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
from mcp.types import Resource, Tool
from pydantic import AnyUrl

from .server_tools import TOOL_REGISTRY
from .startup import verify_api_on_startup

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
# Dynamic FastMCP Tool Registration
# ============================================================================


# Register all tools dynamically from the registry
def register_tools():
    """Register all tools from the registry with FastMCP."""
    for tool_name, tool_config in TOOL_REGISTRY.items():
        schema = tool_config["schema"]
        handler_func = tool_config["handler"]
        description = tool_config["description"]
        annotations = tool_config.get("annotations")

        # Create the async handler function with proper schema annotation
        async def create_handler(arguments, handler=handler_func):
            return await handler(arguments.model_dump())

        # Set proper metadata
        create_handler.__name__ = tool_name
        create_handler.__doc__ = description
        create_handler.__annotations__ = {"arguments": schema}

        # Register with FastMCP (annotations passed via decorator kwargs)
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
            "version": "1.1.0",
            "description": "MCP server for Gramps Web API genealogy operations",
            "mcp_endpoint": "/mcp",
            "tools_count": len(TOOL_REGISTRY),
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
            "tools": len(TOOL_REGISTRY),
        }
    )


async def run_stdio_server():
    """Run the MCP server with stdio transport."""
    await verify_api_on_startup()

    # Create a standard MCP server for stdio transport
    server = Server("gramps")

    @server.list_tools()
    async def handle_list_tools():
        """List all available tools."""
        return [
            Tool(
                name=tool_name,
                description=tool_config["description"],
                inputSchema=tool_config["schema"].model_json_schema(),
                annotations=tool_config.get("annotations"),
            )
            for tool_name, tool_config in TOOL_REGISTRY.items()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls."""
        if name in TOOL_REGISTRY:
            return await TOOL_REGISTRY[name]["handler"](arguments)
        else:
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
