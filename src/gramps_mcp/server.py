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
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, ToolAnnotations
from pydantic import AnyUrl, BaseModel, Field

# Import all parameter models
from .models.parameters.citation_params import CitationData
from .models.parameters.event_params import EventSaveParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaSaveParams
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.simple_params import (
    DeleteParams,
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams

# Import all tool functions
from .models.parameters.tag_params import TagSaveParams, TagSearchParams
from .models.parameters.transactions_params import TransactionHistoryParams
from .tools import (
    delete_tool,
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
    list_tags_tool,
    search_text_tool,
    upsert_citation_tool,
    upsert_event_tool,
    upsert_family_tool,
    upsert_media_tool,
    upsert_note_tool,
    upsert_person_tool,
    upsert_place_tool,
    upsert_repository_tool,
    upsert_source_tool,
    upsert_tag_tool,
)
from .tools.search_basic import search_tool
from .tools.search_details import get_tool


# Simple analysis models for tools that use direct dict access
class TreeInfoParams(BaseModel):
    include_statistics: bool = Field(True, description="Include statistics")


class DescendantsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


# Setup logging — MCP-15: stdio transport uses stdout as the JSON-RPC channel,
# so all logging MUST go to stderr.
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


# MCP-5: Tool annotation presets for read, write, and delete operations.
# All tools set openWorldHint=True (external Gramps Web API).
_READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
_WRITE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
_DELETE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

# Tool registry - single source of truth for all tools
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Search & Retrieval Tools
    "search": {
        "description": (
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax"
        ),
        "schema": SimpleFindParams,
        "handler": search_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "search_text": {
        "description": (
            "Text search across all record types - matches literal text "
            "within records, not logical combinations"
        ),
        "schema": SimpleSearchParams,
        "handler": search_text_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get": {
        "description": "Get full details for any entity by handle or gramps_id",
        "schema": SimpleGetParams,
        "handler": get_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    # Data Management Tools
    "upsert_person": {
        "description": (
            "Create or update person information including family links, "
            "event associations, and alternate names (AKA, married names)"
        ),
        "schema": PersonData,
        "handler": upsert_person_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_family": {
        "description": "Create or update family unit including member relationships",
        "schema": FamilySaveParams,
        "handler": upsert_family_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_event": {
        "description": (
            "Create or update life event including person/place associations"
        ),
        "schema": EventSaveParams,
        "handler": upsert_event_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_place": {
        "description": "Create or update geographic location",
        "schema": PlaceSaveParams,
        "handler": upsert_place_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_source": {
        "description": "Create or update source document",
        "schema": SourceSaveParams,
        "handler": upsert_source_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_citation": {
        "description": "Create or update citation including object associations",
        "schema": CitationData,
        "handler": upsert_citation_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_note": {
        "description": "Create or update textual note including object associations",
        "schema": NoteSaveParams,
        "handler": upsert_note_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_media": {
        "description": "Create or update media files including object associations",
        "schema": MediaSaveParams,
        "handler": upsert_media_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_repository": {
        "description": "Create or update repository information",
        "schema": RepositoryData,
        "handler": upsert_repository_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "delete": {
        "description": "Delete any entity by type and handle",
        "schema": DeleteParams,
        "handler": delete_tool,
        "annotations": _DELETE_ANNOTATIONS,
    },
    # Tag Management Tools
    "upsert_tag": {
        "description": "Create or update a tag with name and color",
        "schema": TagSaveParams,
        "handler": upsert_tag_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "list_tags": {
        "description": "List all tags in the family tree",
        "schema": TagSearchParams,
        "handler": list_tags_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    # Analysis Tools
    "get_tree_stats": {
        "description": (
            "Get information about a specific tree including statistics "
            "(counts of people, families, events, etc.)"
        ),
        "schema": TreeInfoParams,
        "handler": get_tree_stats_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get_descendants": {
        "description": (
            "Find all descendants of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": DescendantsParams,
        "handler": get_descendants_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get_ancestors": {
        "description": (
            "Find all ancestors of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": AncestorsParams,
        "handler": get_ancestors_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get_recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
        "annotations": _READ_ANNOTATIONS,
    },
}


# Create FastMCP app with stateless HTTP (no SSE)
app = FastMCP("gramps", stateless_http=True, json_response=True)


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
        # MCP-20: default to loopback; use GRAMPS_MCP_HOST=0.0.0.0 for Docker
        app.settings.host = os.environ.get("GRAMPS_MCP_HOST", "127.0.0.1")
        app.settings.port = int(os.environ.get("GRAMPS_MCP_PORT", "8000"))

        # Run with streamable-http transport for production use
        app.run(transport="streamable-http")
