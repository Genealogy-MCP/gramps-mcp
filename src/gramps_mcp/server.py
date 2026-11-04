# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
MCP server main entry point with HTTP transport.

This module provides the FastAPI application and MCP server setup with
genealogy tools for Gramps Web API integration.
"""

import asyncio
import logging
import os
import re
import sys
from typing import Any

from mcp.server import Server
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Resource, TextContent, Tool, ToolAnnotations
from mcp_codemode import (
    ExecuteOperationParams,
    SearchOperationsParams,
    execute_operation,
    format_search_results,
    search_operations,
)
from pydantic import AnyUrl

from . import __version__
from .client import get_client
from .operations import OPERATION_REGISTRY
from .startup import verify_api_on_startup
from .tools._identifier import normalize_identifier

# Setup logging — MCP-15: stdio transport uses stdout as the JSON-RPC channel,
# so all logging MUST go to stderr.
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

_ORIGIN_PATTERN = re.compile(r"https?://[^/?#\s]+")


def _split_entries(raw: str) -> list[str]:
    """Split a comma-separated env var value, dropping blank entries."""
    return [entry.strip() for entry in raw.split(",") if entry.strip()]


def transport_security(
    allowed_hosts: str, allowed_origins: str
) -> TransportSecuritySettings:
    """Build the /mcp DNS-rebinding guard: localhost plus extra hosts and origins.

    Args:
        allowed_hosts (str): Comma-separated Host header values, the raw
            GRAMPS_MCP_ALLOWED_HOSTS value. ``name:*`` matches any port.
        allowed_origins (str): Comma-separated Origin header values, the raw
            GRAMPS_MCP_ALLOWED_ORIGINS value. ``scheme://name:*`` matches any
            port.

    Returns:
        TransportSecuritySettings: Settings that reject any other Host header
            with HTTP 421 and any other Origin header with HTTP 403.

    Raises:
        ValueError: If a host entry is a URL, or an origin entry is not a bare
            http(s)://host[:port].
    """
    extra_hosts = _split_entries(allowed_hosts)
    for entry in extra_hosts:
        if "/" in entry:
            raise ValueError(
                f"GRAMPS_MCP_ALLOWED_HOSTS entry {entry!r} is a URL; list bare "
                "Host header values such as 'gramps-mcp:8000' or 'mcp.example.com'."
            )
    extra_origins = _split_entries(allowed_origins)
    for entry in extra_origins:
        # Reason: a browser Origin is scheme://host[:port] with no path, so an
        # entry with a path or trailing slash would never match any request.
        if not _ORIGIN_PATTERN.fullmatch(entry):
            raise ValueError(
                f"GRAMPS_MCP_ALLOWED_ORIGINS entry {entry!r} is not an origin; "
                "list values such as 'https://mcp.example.com' with no path "
                "or trailing slash."
            )
    # Reason: these are the MCP SDK's own localhost defaults, written out
    # because passing transport_security explicitly replaces them.
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *extra_hosts],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
            *extra_origins,
        ],
    )


# Create FastMCP app with stateless HTTP (no SSE)
app = FastMCP(
    "gramps",
    stateless_http=True,
    json_response=True,
)


# ============================================================================
# Code Mode: 2 Meta-Tool Registration (MCP-29)
# ============================================================================


def _register_tools(mcp: FastMCP) -> None:
    """Register search + execute meta-tools using library functions.

    Uses mcp.types.ToolAnnotations directly to avoid the library's
    lightweight ToolAnnotations dataclass incompatibility with newer
    FastMCP versions (library bug, tracked upstream).
    """

    @mcp.tool(
        name="search",
        description=(
            "Discover available operations and their parameters. "
            "Call with a top-level 'query' string (not inside params). "
            "Returns matching operations with parameter schemas. "
            "Always use this before calling 'execute' to find the correct "
            "operation name."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def search(arguments: SearchOperationsParams) -> list[TextContent]:
        matches = search_operations(
            arguments.query,
            OPERATION_REGISTRY,
            category=arguments.category,
        )
        text = format_search_results(matches, OPERATION_REGISTRY)
        return [TextContent(type="text", text=text)]

    @mcp.tool(
        name="execute",
        description=(
            "Run a named operation against the Gramps Web API. "
            "Operations use generic names with a type parameter -- "
            "e.g. operation='get' with params.type='media', NOT 'get_media'. "
            "Use 'search' first to discover the exact operation name and its "
            "params schema, then call this with "
            "{operation: '...', params: {...}}."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def execute(
        ctx: Context[Any, Any, Any],
        arguments: ExecuteOperationParams,
    ) -> list[Any]:
        args_dict = arguments.model_dump()
        # Pre-validation hook: normalize identifier before library validates
        entry = OPERATION_REGISTRY.get(args_dict.get("operation", ""))
        if entry is not None:
            args_dict["params"] = normalize_identifier(
                args_dict["params"], entry.params_schema
            )
        return await execute_operation(args_dict, OPERATION_REGISTRY, ctx)


_register_tools(app)


# ============================================================================
# Resource Management
# ============================================================================


def load_resource(filename: str) -> str:
    """Load content from resources folder.

    Raises on failure so MCP clients see an error, not an error string
    that looks like valid content (MCP-13).

    Args:
        filename: Name of the file in the resources/ directory.

    Returns:
        str: File content.

    Raises:
        FileNotFoundError: If the resource file does not exist.
        OSError: If the resource file cannot be read.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    resource_path = os.path.join(current_dir, "resources", filename)

    with open(resource_path, "r", encoding="utf-8") as f:
        return f.read()


@app.resource("gql://documentation")
def get_gql_documentation() -> str:
    """
    Complete GQL documentation, syntax, examples, and property
    reference for Gramps queries.
    """
    return load_resource("gql-documentation.md")


@app.resource("gramps://usage-guide")
def get_usage_guide() -> str:
    """
    IMPORTANT: Read this first before using ANY creation tools -
    explains proper genealogy workflow and tool usage order.
    """
    return load_resource("gramps-usage-guide.md")


# Add custom routes to the FastMCP app
@app.custom_route("/", ["GET"])
async def root(request):
    """Root endpoint with server information."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "service": "Gramps MCP Server",
            "version": __version__,
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": len(await app.list_tools()),
            "operations_count": len(OPERATION_REGISTRY),
        }
    )


@app.custom_route("/health", ["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "status": "healthy",
            "service": "Gramps MCP Server",
            "tools": len(await app.list_tools()),
            "operations": len(OPERATION_REGISTRY),
        }
    )


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    await verify_api_on_startup()

    # Create a standard MCP server for stdio transport
    server = Server("gramps")

    # Build tool definitions from the registered meta-tools
    _STDIO_TOOLS = {
        "search": {
            "schema": SearchOperationsParams,
            "description": (
                "Discover available operations and their parameters. "
                "Call with a top-level 'query' string (not inside params). "
                "Returns matching operations with parameter schemas. "
                "Always use this before calling 'execute' to find the correct "
                "operation name."
            ),
            "annotations": ToolAnnotations(
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        },
        "execute": {
            "schema": ExecuteOperationParams,
            "description": (
                "Run a named operation against the Gramps Web API. "
                "Operations use generic names with a type parameter -- "
                "e.g. operation='get' with params.type='media', NOT 'get_media'. "
                "Use 'search' first to discover the exact operation name and its "
                "params schema, then call this with "
                "{operation: '...', params: {...}}."
            ),
            "annotations": ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=False,
                openWorldHint=True,
            ),
        },
    }

    @server.list_tools()
    async def handle_list_tools():
        """List the 2 Code Mode meta-tools."""
        return [
            Tool(
                name=tool_name,
                description=tool_config["description"],
                inputSchema=tool_config["schema"].model_json_schema(),
                annotations=tool_config["annotations"],
            )
            for tool_name, tool_config in _STDIO_TOOLS.items()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls for the 2 meta-tools."""
        if name == "search":
            matches = search_operations(
                arguments.get("query", ""),
                OPERATION_REGISTRY,
                category=arguments.get("category"),
            )
            text = format_search_results(matches, OPERATION_REGISTRY)
            return [TextContent(type="text", text=text)]
        elif name == "execute":
            # Pre-validation hook: normalize identifier
            entry = OPERATION_REGISTRY.get(arguments.get("operation", ""))
            if entry is not None and "params" in arguments:
                arguments["params"] = normalize_identifier(
                    arguments["params"], entry.params_schema
                )
            return await execute_operation(arguments, OPERATION_REGISTRY, None)
        raise ValueError(f"Unknown tool: {name}")

    # Resource definitions for stdio transport
    STDIO_RESOURCES = [
        Resource(
            uri=AnyUrl("gql://documentation"),
            name="GQL Documentation",
            description=(
                "Complete GQL documentation, syntax, examples, and property "
                "reference for Gramps queries."
            ),
            mimeType="text/markdown",
        ),
        Resource(
            uri=AnyUrl("gramps://usage-guide"),
            name="Gramps Usage Guide",
            description=(
                "IMPORTANT: Read this first before using ANY creation tools - "
                "explains proper genealogy workflow and tool usage order."
            ),
            mimeType="text/markdown",
        ),
    ]

    RESOURCE_FILE_MAP = {
        "gql://documentation": "gql-documentation.md",
        "gramps://usage-guide": "gramps-usage-guide.md",
    }

    @server.list_resources()
    async def handle_list_resources():
        """List available resources."""
        return STDIO_RESOURCES

    @server.read_resource()
    async def handle_read_resource(uri: AnyUrl) -> str:
        """Read a resource by URI."""
        uri_str = str(uri)
        filename = RESOURCE_FILE_MAP.get(uri_str)
        if not filename:
            raise ValueError(f"Unknown resource: {uri_str}")
        return load_resource(filename)

    # Run the server with stdio transport
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        await get_client().close()


def configure_http(mcp: FastMCP) -> None:
    """Apply the GRAMPS_MCP_* HTTP environment variables to a FastMCP app.

    Call before serving: the session manager reads these settings when the
    HTTP app is first built.

    Args:
        mcp (FastMCP): The app to configure.
    """
    # MCP-20: default to loopback; use GRAMPS_MCP_HOST=0.0.0.0 for Docker
    mcp.settings.host = os.environ.get("GRAMPS_MCP_HOST", "127.0.0.1")
    # Reason: `or` treats a set-but-empty variable as unset, matching the
    # ${GRAMPS_MCP_PORT:-8000} fallback in Compose and the healthcheck (#135).
    port = os.environ.get("GRAMPS_MCP_PORT") or "8000"
    try:
        mcp.settings.port = int(port)
    except ValueError:
        raise ValueError(
            f"GRAMPS_MCP_PORT must be an integer port number such as 8000, got {port!r}"
        ) from None
    # Reason: FastMCP fixed its Host allow-list at construction from the
    # default 127.0.0.1 host, so changing settings.host above leaves it as is.
    mcp.settings.transport_security = transport_security(
        os.environ.get("GRAMPS_MCP_ALLOWED_HOSTS", ""),
        os.environ.get("GRAMPS_MCP_ALLOWED_ORIGINS", ""),
    )


async def run_http_server():
    """Run the FastMCP server with streamable HTTP transport.

    Verifies the API version once, before serving, and closes the shared API
    client once, after the server stops.

    Reason: with stateless_http=True FastMCP enters its lifespan once per
    HTTP request, so neither step can live there (MCP-21, #121).
    """
    await verify_api_on_startup()
    try:
        await app.run_streamable_http_async()
    finally:
        await get_client().close()


if __name__ == "__main__":
    # Determine transport type from command line arguments or environment
    transport_type = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"

    if transport_type == "stdio":
        # Run with stdio transport for CLI usage
        asyncio.run(run_stdio_server())
    else:
        configure_http(app)
        asyncio.run(run_http_server())
