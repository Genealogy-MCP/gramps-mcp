# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Detail retrieval MCP tools for genealogy operations.

This module contains detail retrieval tools for getting comprehensive
entity information using direct API calls.
"""

import logging
from typing import Any, Dict, List

from mcp.types import TextContent

from ..config import get_settings
from ..handlers.citation_handler import format_citation
from ..handlers.event_handler import format_event
from ..handlers.family_detail_handler import format_family_detail
from ..handlers.media_handler import format_media
from ..handlers.note_handler import format_note
from ..handlers.person_detail_handler import format_person_detail
from ..handlers.place_handler import format_place
from ..handlers.repository_handler import format_repository
from ..handlers.source_handler import format_source
from ._compat import extract_arguments
from ._errors import McpToolError, raise_tool_error
from .search_basic import with_client

logger = logging.getLogger(__name__)


@with_client
async def get_person_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Get comprehensive person information using direct API calls.
    """
    handle = arguments.get("person_handle")
    try:
        if not handle:
            raise ValueError("person_handle is required")

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        formatted_person = await format_person_detail(client, tree_id, handle)

        return [TextContent(type="text", text=formatted_person)]

    except Exception as e:
        raise_tool_error(
            e,
            "person details retrieval",
            entity_type="person",
            identifier=handle,
        )


@with_client
async def get_family_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Get detailed family information using direct API calls.
    """
    handle = arguments.get("family_handle")
    try:
        if not handle:
            raise ValueError("family_handle is required")

        # Get tree_id from settings
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        formatted_family = await format_family_detail(client, tree_id, handle)

        return [TextContent(type="text", text=formatted_family)]

    except Exception as e:
        raise_tool_error(
            e,
            "family details retrieval",
            entity_type="family",
            identifier=handle,
        )


@with_client
async def get_event_tool(client, arguments: Dict) -> List[TextContent]:
    """Get event details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_event(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted or "No event data found.")]
    except Exception as e:
        raise_tool_error(
            e, "event details retrieval", entity_type="event", identifier=handle
        )


@with_client
async def get_place_tool(client, arguments: Dict) -> List[TextContent]:
    """Get place details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_place(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted)]
    except Exception as e:
        raise_tool_error(
            e, "place details retrieval", entity_type="place", identifier=handle
        )


@with_client
async def get_source_tool(client, arguments: Dict) -> List[TextContent]:
    """Get source details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_source(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted)]
    except Exception as e:
        raise_tool_error(
            e, "source details retrieval", entity_type="source", identifier=handle
        )


@with_client
async def get_citation_tool(client, arguments: Dict) -> List[TextContent]:
    """Get citation details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_citation(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted)]
    except Exception as e:
        raise_tool_error(
            e, "citation details retrieval", entity_type="citation", identifier=handle
        )


@with_client
async def get_note_tool(client, arguments: Dict) -> List[TextContent]:
    """Get note details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_note(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted)]
    except Exception as e:
        raise_tool_error(
            e, "note details retrieval", entity_type="note", identifier=handle
        )


@with_client
async def get_media_tool(client, arguments: Dict) -> List[TextContent]:
    """Get media details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_media(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted)]
    except Exception as e:
        raise_tool_error(
            e, "media details retrieval", entity_type="media", identifier=handle
        )


@with_client
async def get_repository_tool(client, arguments: Dict) -> List[TextContent]:
    """Get repository details by handle."""
    handle = arguments.get("handle")
    try:
        if not handle:
            raise ValueError("handle is required")
        settings = get_settings()
        formatted = await format_repository(client, settings.gramps_tree_id, handle)
        return [TextContent(type="text", text=formatted)]
    except Exception as e:
        raise_tool_error(
            e,
            "repository details retrieval",
            entity_type="repository",
            identifier=handle,
        )


# Dispatch map for entity types beyond person/family
_GET_TOOL_DISPATCH = {
    "event": get_event_tool,
    "place": get_place_tool,
    "source": get_source_tool,
    "citation": get_citation_tool,
    "note": get_note_tool,
    "media": get_media_tool,
    "repository": get_repository_tool,
}


def _stub_if_empty(
    result: List[TextContent], entity_type: str, handle: str
) -> List[TextContent]:
    """Substitute a stub when a formatter produced nothing to display.

    A record that formats to a zero-length string leaves the caller with a
    response indistinguishable from a transport failure (issue #79).

    The wording deliberately does not assert that the record exists: the
    handlers collapse a 404 into "" as well, so this layer cannot tell
    "no displayable fields" from "no such handle".
    """
    if any(item.text.strip() for item in result):
        return result

    return [
        TextContent(
            type="text",
            text=(
                f"{entity_type} [{handle}] returned no displayable content. "
                f"Either every field is empty or private, or the handle does "
                f"not exist. Use search to verify the record.\n"
            ),
        )
    ]


async def get_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """Universal get tool for any entity type by handle or gramps_id."""
    arguments = extract_arguments(ctx, params)
    entity_type = arguments.get("type")
    handle = arguments.get("handle")
    gramps_id = arguments.get("gramps_id")

    if not entity_type:
        valid_types = sorted(list(_GET_TOOL_DISPATCH.keys()) + ["person", "family"])
        raise McpToolError(
            f"Missing required parameter 'type'. Valid types: {', '.join(valid_types)}"
        )

    # If gramps_id provided but no handle, find the handle first.
    # Use the native ?gramps_id= filter, not gql=: Gramps Web API 3.x
    # returns HTTP 500 for any gql= query on /api/notes/ (issue #69),
    # and the native filter is the simpler request for a plain equality.
    if gramps_id and not handle:
        # Read the handle from the raw API response, not from formatted
        # search text -- formatters return "" for sparse records (e.g. a
        # note with an empty text body, issue #78).
        from ._resolve import resolve_gramps_id

        handle = await resolve_gramps_id(entity_type, gramps_id)

    if not handle:
        raise McpToolError(
            f"Could not resolve handle for {entity_type} "
            f"(gramps_id={gramps_id}). Use search to verify the ID exists."
        )

    # Person and family use detailed handlers with timelines
    if entity_type == "person":
        result = await get_person_tool({"person_handle": handle})
        return _stub_if_empty(result, entity_type, handle)
    elif entity_type == "family":
        result = await get_family_tool({"family_handle": handle})
        return _stub_if_empty(result, entity_type, handle)

    # All other entity types use their basic format handlers
    tool_func = _GET_TOOL_DISPATCH.get(entity_type)
    if tool_func:
        result = await tool_func({"handle": handle})
        return _stub_if_empty(result, entity_type, handle)

    valid_types = sorted(list(_GET_TOOL_DISPATCH.keys()) + ["person", "family"])
    raise McpToolError(
        f"Entity type '{entity_type}' not supported for get. "
        f"Valid types: {', '.join(valid_types)}"
    )
