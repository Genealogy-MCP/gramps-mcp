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
Basic search MCP tools for genealogy operations.

This module contains search tools for finding entities by type, full-text
search, and tag listing.
"""

import functools
import logging
from typing import Callable, Dict, List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..handlers.citation_handler import format_citation
from ..handlers.event_handler import format_event
from ..handlers.family_handler import format_family
from ..handlers.media_handler import format_media
from ..handlers.note_handler import format_note
from ..handlers.person_handler import format_person
from ..handlers.place_handler import format_place
from ..handlers.repository_handler import format_repository
from ..handlers.source_handler import format_source
from ..models.api_calls import ApiCalls
from ..models.parameters.base_params import BaseGetMultipleParams
from ..models.parameters.citation_params import GetCitationsParams
from ..models.parameters.event_params import EventSearchParams
from ..models.parameters.media_params import MediaSearchParams
from ..models.parameters.note_params import NotesParams
from ..models.parameters.place_params import PlaceSearchParams
from ..models.parameters.repository_params import RepositoriesParams
from ..models.parameters.search_params import SearchParams
from ..models.parameters.source_params import SourceSearchParams
from ._errors import McpToolError, raise_tool_error
from ._gql_hints import gql_hint

logger = logging.getLogger(__name__)

# Shared dispatch: entity type -> format handler.
# Used by search_basic and data_management.
FORMATTER_DISPATCH: Dict[str, Callable] = {
    "person": format_person,
    "family": format_family,
    "event": format_event,
    "place": format_place,
    "source": format_source,
    "citation": format_citation,
    "media": format_media,
    "note": format_note,
    "repository": format_repository,
}


def with_client(func: Callable) -> Callable:
    """
    Decorator that provides a GrampsWebAPIClient instance and handles cleanup.

    The decorated function will receive 'client' as the first argument.
    Client is automatically closed after function execution.

    Args:
        func: Async function to decorate

    Returns:
        Decorated function with client management
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        client = GrampsWebAPIClient()
        try:
            return await func(client, *args, **kwargs)
        finally:
            await client.close()

    return wrapper


async def format_search_result_by_type(client, item: Dict) -> str:
    """
    Format search result using appropriate handler based on object type.

    Args:
        client: Gramps API client instance
        item (Dict): Search result item containing object_type and object data

    Returns:
        str: Formatted result string using the appropriate handler
    """
    obj_type = item.get("object_type", "").lower()
    obj = item.get("object", {})
    handle = obj.get("handle", "")

    if not handle:
        return f"• **{obj_type.title()} record** (No handle available)\n\n"

    settings = get_settings()
    tree_id = settings.gramps_tree_id

    try:
        formatter = FORMATTER_DISPATCH.get(obj_type)
        if formatter:
            result = await formatter(client, tree_id, handle)
            return result or ""

        gramps_id = obj.get("gramps_id", "N/A")
        title = (
            obj.get("title", "") or obj.get("desc", "") or f"{obj_type.title()} record"
        )
        return f"• **{title}** ({obj_type.title()} - ID: {gramps_id})\n\n"
    except Exception as e:
        logger.debug(f"Error formatting {obj_type} result: {e}")
        gramps_id = obj.get("gramps_id", "N/A")
        return (
            f"• **{obj_type.title()} record** (ID: {gramps_id}) - "
            "Error formatting details\n\n"
        )


async def _search_entities(
    client,
    arguments: Dict,
    params_class,
    api_call: ApiCalls,
    entity_type: str,
    format_handler,
) -> List[TextContent]:
    """
    Generic search function for all entity types.

    Args:
        client: Gramps API client instance
        arguments: Search parameters dictionary
        params_class: Pydantic model class for parameter validation
        api_call: ApiCalls enum value for the API endpoint
        entity_type: Human-readable entity type for error messages
        format_handler: Async function to format individual results

    Returns:
        List of TextContent with formatted search results
    """
    try:
        params = params_class(**arguments)

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        response = await client.make_api_call(
            api_call=api_call, params=params, tree_id=tree_id
        )

        if isinstance(response, list):
            results = response
            total_count = len(results)
        else:
            results = response.get("data", [])
            total_count = response.get("total_count", len(results))

        if not results:
            hint = gql_hint(entity_type, arguments.get("gql", ""))
            msg = f"No {entity_type} found"
            if hint:
                msg += f"\n\nHint: {hint}"
            formatted_results = msg
        else:
            actual_total = total_count if total_count is not None else len(results)

            # Apply pagesize ceiling before formatting
            results_to_display = (
                results[: params.pagesize] if params.pagesize else results
            )

            # Collect non-empty formatted items (empty = handler signalled skip)
            formatted_items = []
            for item in results_to_display:
                if not isinstance(item, dict):
                    continue

                # Extract object from search result wrapper if needed
                obj = item.get("object", item)
                handle = obj.get("handle", "")

                if handle:
                    item_formatted = await format_handler(client, tree_id, handle)
                    if item_formatted:
                        formatted_items.append(item_formatted)

            # Header is built after formatting so it reflects what was actually shown
            shown = len(formatted_items)
            if actual_total > shown:
                header = f"Found {actual_total} {entity_type} (showing {shown}):\n\n"
            else:
                header = f"Found {shown} {entity_type}:\n\n"

            formatted_results = header + "".join(formatted_items)

        return [TextContent(type="text", text=formatted_results)]

    except Exception as e:
        hint = gql_hint(entity_type, arguments.get("gql", ""))
        context = f"{entity_type} search"
        if hint:
            context += f"\n\nGQL hint: {hint}"
        raise_tool_error(e, context)


@with_client
async def search_person_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for people by name, ID, or other criteria.

    Returns limited info: name, birth/death dates and places.
    """
    return await _search_entities(
        client,
        arguments,
        BaseGetMultipleParams,
        ApiCalls.GET_PEOPLE,
        "people",
        format_person,
    )


@with_client
async def search_family_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for families (family units).

    Returns limited info: family members' names, marriage date/place.
    """
    return await _search_entities(
        client,
        arguments,
        BaseGetMultipleParams,
        ApiCalls.GET_FAMILIES,
        "families",
        format_family,
    )


@with_client
async def search_event_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for life events (births, deaths, marriages).
    """
    return await _search_entities(
        client,
        arguments,
        EventSearchParams,
        ApiCalls.GET_EVENTS,
        "events",
        format_event,
    )


@with_client
async def search_place_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Find geographic locations and places.
    """
    return await _search_entities(
        client,
        arguments,
        PlaceSearchParams,
        ApiCalls.GET_PLACES,
        "places",
        format_place,
    )


@with_client
async def search_source_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for source materials and documents.
    """
    return await _search_entities(
        client,
        arguments,
        SourceSearchParams,
        ApiCalls.GET_SOURCES,
        "sources",
        format_source,
    )


@with_client
async def search_repository_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for repositories (archives, libraries, churches, etc.).
    """
    return await _search_entities(
        client,
        arguments,
        RepositoriesParams,
        ApiCalls.GET_REPOSITORIES,
        "repositories",
        format_repository,
    )


@with_client
async def search_media_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Find photos, documents, and media files.
    """
    return await _search_entities(
        client,
        arguments,
        MediaSearchParams,
        ApiCalls.GET_MEDIA,
        "media files",
        format_media,
    )


@with_client
async def search_citation_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for citations and references, showing source details, URLs, and
    repository info.
    """
    return await _search_entities(
        client,
        arguments,
        GetCitationsParams,
        ApiCalls.GET_CITATIONS,
        "citations",
        format_citation,
    )


@with_client
async def search_note_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Search for notes and research notes.
    """
    return await _search_entities(
        client, arguments, NotesParams, ApiCalls.GET_NOTES, "notes", format_note
    )


@with_client
async def list_tags_tool(client, arguments: Dict) -> List[TextContent]:
    """
    List all tags in the family tree.

    Args:
        client: Gramps API client instance
        arguments: Search parameters (page, pagesize, sort).

    Returns:
        List of TextContent with formatted tag listing.
    """
    try:
        from ..models.parameters.tag_params import TagSearchParams

        params = TagSearchParams(**arguments)
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        response = await client.make_api_call(
            api_call=ApiCalls.GET_TAGS, params=params, tree_id=tree_id
        )

        results = response if isinstance(response, list) else response.get("data", [])

        if not results:
            return [TextContent(type="text", text="No tags found.")]

        formatted = f"Found {len(results)} tags:\n\n"
        for tag in results:
            name = tag.get("name", "Unknown")
            handle = tag.get("handle", "N/A")
            color = tag.get("color", "None")
            priority = tag.get("priority", 0)
            formatted += (
                f"- **{name}** [{handle}] (color: {color}, priority: {priority})\n"
            )

        return [TextContent(type="text", text=formatted)]

    except Exception as e:
        raise_tool_error(e, "tag search")


# Explicit dispatch for search_tool — avoids globals() lookup (MCP-18).
_SEARCH_TOOL_DISPATCH: Dict[str, Callable] = {
    "person": search_person_tool,
    "family": search_family_tool,
    "event": search_event_tool,
    "place": search_place_tool,
    "source": search_source_tool,
    "citation": search_citation_tool,
    "media": search_media_tool,
    "note": search_note_tool,
    "repository": search_repository_tool,
}


async def search_tool(arguments: Dict) -> List[TextContent]:
    """Universal type-based search tool."""
    entity_type = arguments.get("type")
    gql = arguments.get("gql")
    max_results = arguments.get("max_results", 20)

    if not entity_type:
        valid_types = ", ".join(sorted(_SEARCH_TOOL_DISPATCH.keys()))
        raise McpToolError(f"Entity type is required. Valid types: {valid_types}")

    entity_type_str = (
        entity_type.value if hasattr(entity_type, "value") else entity_type
    )

    params = {"gql": gql, "pagesize": max_results}

    tool_func = _SEARCH_TOOL_DISPATCH.get(entity_type_str)
    if tool_func:
        return await tool_func(params)

    valid_types = ", ".join(sorted(_SEARCH_TOOL_DISPATCH.keys()))
    raise McpToolError(
        f"Entity type '{entity_type}' not supported for search. "
        f"Valid types: {valid_types}"
    )


@with_client
async def search_text_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Full-text search across all entity types.
    """
    try:
        params = SearchParams(**arguments)

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        response, headers = await client.make_api_call(
            api_call=ApiCalls.GET_SEARCH,
            params=params,
            tree_id=tree_id,
            with_headers=True,
        )

        if isinstance(response, list):
            results = response
        else:
            results = response.get("data", [])

        total_count = int(headers.get("x-total-count", len(results)))

        if not results:
            formatted_results = f"No records found matching '{params.query}'"
        else:
            actual_total = total_count if total_count is not None else len(results)
            displayed_count = len(results)

            if actual_total > displayed_count:
                header = (
                    f"Found {actual_total} records matching '{params.query}' "
                    f"(showing {displayed_count}):\n\n"
                )
            else:
                header = f"Found {actual_total} records matching '{params.query}':\n\n"

            formatted_results = header

            results_to_display = (
                results[: params.pagesize] if params.pagesize else results
            )
            for item in results_to_display:
                if not isinstance(item, dict):
                    continue

                result_formatted = await format_search_result_by_type(client, item)
                formatted_results += result_formatted

        return [TextContent(type="text", text=formatted_results)]

    except Exception as e:
        raise_tool_error(e, "full-text search")
