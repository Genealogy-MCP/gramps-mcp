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
Detail retrieval MCP tools for genealogy operations.

This module contains detail retrieval tools for getting comprehensive
entity information using direct API calls.
"""

import logging
from typing import Dict, List

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
from ._errors import raise_tool_error
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


async def get_tool(arguments: Dict) -> List[TextContent]:
    """Universal get tool for any entity type by handle or gramps_id."""
    entity_type = arguments.get("type")
    handle = arguments.get("handle")
    gramps_id = arguments.get("gramps_id")

    # If gramps_id provided but no handle, find the handle first
    if gramps_id and not handle:
        from .search_basic import search_tool

        search_result = await search_tool(
            {"type": entity_type, "gql": f'gramps_id="{gramps_id}"', "max_results": 1}
        )

        # Extract handle from search result
        search_text = search_result[0].text
        import re

        handle_match = re.search(r"\[([^\]]+)\]", search_text)
        if handle_match:
            handle = handle_match.group(1)

    if not handle:
        return [
            TextContent(
                type="text",
                text=f"Could not resolve handle for {entity_type} "
                f"(gramps_id={gramps_id})",
            )
        ]

    # Person and family use detailed handlers with timelines
    if entity_type == "person":
        return await get_person_tool({"person_handle": handle})
    elif entity_type == "family":
        return await get_family_tool({"family_handle": handle})

    # All other entity types use their basic format handlers
    tool_func = _GET_TOOL_DISPATCH.get(str(entity_type))
    if tool_func:
        return await tool_func({"handle": handle})

    return [TextContent(type="text", text=f"Entity type '{entity_type}' not supported")]
