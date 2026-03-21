# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
MCP server main entry point with HTTP transport.

This module provides the FastAPI application and MCP server setup with
genealogy tools for Gramps Web API integration.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, ToolAnnotations
from pydantic import AnyUrl

from .operations import OPERATION_REGISTRY
from .startup import verify_api_on_startup
from .tools.meta_execute import ExecuteOperationParams, execute_operation_tool
from .tools.meta_search import SearchOperationsParams, search_operations_tool

# Setup logging — MCP-15: stdio transport uses stdout as the JSON-RPC channel,
# so all logging MUST go to stderr.
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def server_lifespan(_app):
    """FastMCP lifespan hook -- verify API version before accepting connections."""
    await verify_api_on_startup()
    yield


# Create FastMCP app with stateless HTTP (no SSE)
app = FastMCP(
    "gramps",
    stateless_http=True,
    json_response=True,
    lifespan=server_lifespan,
)


# ============================================================================
# Code Mode: 2 Meta-Tool Registration (MCP-29)
# ============================================================================

_META_TOOLS = {
    "search": {
        "schema": SearchOperationsParams,
        "handler": search_operations_tool,
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
        "handler": execute_operation_tool,
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


def register_tools() -> None:
    """Register the 2 Code Mode meta-tools with FastMCP."""
    for tool_name, tool_config in _META_TOOLS.items():
        schema = tool_config["schema"]
        handler_func = tool_config["handler"]
        description = tool_config["description"]
        annotations = tool_config["annotations"]

        async def create_handler(arguments, handler=handler_func):
            return await handler(arguments.model_dump())

        create_handler.__name__ = tool_name
        create_handler.__doc__ = description
        create_handler.__annotations__ = {"arguments": schema}

        app.tool(description=description, annotations=annotations)(create_handler)


register_tools()


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
            "version": "2.0.0",
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": len(_META_TOOLS),
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
            "tools": len(_META_TOOLS),
            "operations": len(OPERATION_REGISTRY),
        }
    )


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    await verify_api_on_startup()

    # Create a standard MCP server for stdio transport
    server = Server("gramps")

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
            for tool_name, tool_config in _META_TOOLS.items()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls for the 2 meta-tools."""
        if name in _META_TOOLS:
            return await _META_TOOLS[name]["handler"](arguments)
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
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    # Determine transport type from command line arguments or environment
    transport_type = sys.argv[1] if len(sys.argv) > 1 else "streamable-http"

    if transport_type == "stdio":
        # Run with stdio transport for CLI usage
        asyncio.run(run_stdio_server())
    else:
        # Run the FastMCP server with streamable HTTP transport
        # API version is verified via server_lifespan hook
        # MCP-20: default to loopback; use GRAMPS_MCP_HOST=0.0.0.0 for Docker
        app.settings.host = os.environ.get("GRAMPS_MCP_HOST", "127.0.0.1")
        app.settings.port = int(os.environ.get("GRAMPS_MCP_PORT", "8000"))

        # Run with streamable-http transport for production use
        app.run(transport="streamable-http")
