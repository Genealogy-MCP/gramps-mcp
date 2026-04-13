# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Data management MCP tools for genealogy operations.

This module contains upsert tools for creating and updating people,
families, events, places, sources, citations, notes, and repositories.
"""

import logging
from typing import Any, List

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from ..models.parameters.citation_params import CitationData
from ..models.parameters.event_params import EventSaveParams
from ..models.parameters.family_params import FamilySaveParams
from ..models.parameters.note_params import NoteSaveParams
from ..models.parameters.people_params import PersonData
from ..models.parameters.place_params import PlaceSaveParams
from ..models.parameters.repository_params import RepositoryData
from ..models.parameters.source_params import SourceSaveParams
from ._compat import extract_arguments
from ._data_helpers import (
    _extract_entity_data,
    _format_save_response,
    _handle_crud_operation,
)
from ._errors import McpToolError, raise_tool_error

__all__ = [
    "upsert_person_tool",
    "upsert_family_tool",
    "upsert_event_tool",
    "upsert_place_tool",
    "upsert_source_tool",
    "upsert_citation_tool",
    "upsert_note_tool",
    "upsert_repository_tool",
]

logger = logging.getLogger(__name__)


async def upsert_person_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update person information including family links and event associations.
    """
    arguments = extract_arguments(ctx, params)
    return await _handle_crud_operation(
        arguments, "person", ApiCalls.POST_PEOPLE, ApiCalls.PUT_PERSON, PersonData
    )


async def upsert_family_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update family unit including member relationships.
    """
    try:
        arguments = extract_arguments(ctx, params)
        validated = FamilySaveParams(**arguments)

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            if validated.handle:
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_FAMILY,
                    params=validated,
                    tree_id=tree_id,
                    handle=validated.handle,
                )
                operation = "updated"
            else:
                result = await client.make_api_call(
                    api_call=ApiCalls.POST_FAMILIES, params=validated, tree_id=tree_id
                )
                operation = "created"

            # family creation response is a list; extract the Family entry
            entity_data = _extract_entity_data(result, "family")
            formatted_response = await _format_save_response(
                client, entity_data, "family", operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "family save")


async def upsert_event_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update life event including person/place associations.
    """
    arguments = extract_arguments(ctx, params)
    return await _handle_crud_operation(
        arguments, "event", ApiCalls.POST_EVENTS, ApiCalls.PUT_EVENT, EventSaveParams
    )


async def upsert_place_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update geographic location.
    """
    arguments = extract_arguments(ctx, params)
    return await _handle_crud_operation(
        arguments, "place", ApiCalls.POST_PLACES, ApiCalls.PUT_PLACE, PlaceSaveParams
    )


async def upsert_source_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update source document.
    """
    arguments = extract_arguments(ctx, params)
    return await _handle_crud_operation(
        arguments,
        "source",
        ApiCalls.POST_SOURCES,
        ApiCalls.PUT_SOURCE,
        SourceSaveParams,
    )


async def upsert_citation_tool(
    ctx: Any = None, params: Any = None
) -> List[TextContent]:
    """
    Create or update citation including object associations.

    Validates that source_handle references an existing Source record
    and that the citation is not self-referencing.
    """
    try:
        arguments = extract_arguments(ctx, params)
        validated = CitationData(**arguments)

        # Self-reference check: citation cannot reference itself as source
        if validated.handle and validated.source_handle:
            if validated.handle == validated.source_handle:
                raise McpToolError(
                    "Citation cannot reference itself as source. "
                    "Set a different source_handle or remove the citation's handle."
                )

        # Source existence check: validate source_handle before write
        if validated.source_handle:
            settings = get_settings()
            tree_id = settings.gramps_tree_id

            client = GrampsWebAPIClient()
            try:
                try:
                    source = await client.make_api_call(
                        api_call=ApiCalls.GET_SOURCE,
                        tree_id=tree_id,
                        handle=validated.source_handle,
                    )
                    if not source:
                        msg = (
                            f"Source with handle '{validated.source_handle}' not "
                            "found. Ensure the source exists before referencing "
                            "it in a citation."
                        )
                        raise McpToolError(msg)
                except GrampsAPIError:
                    msg = (
                        f"Source with handle '{validated.source_handle}' not "
                        "found. Ensure the source exists before referencing "
                        "it in a citation."
                    )
                    raise McpToolError(msg)

                # Validation passed; proceed with normal create/update flow
                if validated.handle:
                    result = await client.make_api_call(
                        api_call=ApiCalls.PUT_CITATION,
                        params=validated,
                        tree_id=tree_id,
                        handle=validated.handle,
                    )
                    operation = "updated"
                else:
                    result = await client.make_api_call(
                        api_call=ApiCalls.POST_CITATIONS,
                        params=validated,
                        tree_id=tree_id,
                    )
                    operation = "created"

                entity_data = _extract_entity_data(result, "citation")
                formatted_response = await _format_save_response(
                    client, entity_data, "citation", operation, tree_id
                )
                return [TextContent(type="text", text=formatted_response)]

            finally:
                await client.close()
        else:
            # No source_handle; proceed with normal create/update flow
            settings = get_settings()
            tree_id = settings.gramps_tree_id

            client = GrampsWebAPIClient()
            try:
                if validated.handle:
                    result = await client.make_api_call(
                        api_call=ApiCalls.PUT_CITATION,
                        params=validated,
                        tree_id=tree_id,
                        handle=validated.handle,
                    )
                    operation = "updated"
                else:
                    result = await client.make_api_call(
                        api_call=ApiCalls.POST_CITATIONS,
                        params=validated,
                        tree_id=tree_id,
                    )
                    operation = "created"

                entity_data = _extract_entity_data(result, "citation")
                formatted_response = await _format_save_response(
                    client, entity_data, "citation", operation, tree_id
                )
                return [TextContent(type="text", text=formatted_response)]

            finally:
                await client.close()

    except McpToolError:
        raise
    except Exception as e:
        raise_tool_error(e, "citation save")


async def upsert_note_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update textual note including object associations.
    """
    arguments = extract_arguments(ctx, params)
    return await _handle_crud_operation(
        arguments, "note", ApiCalls.POST_NOTES, ApiCalls.PUT_NOTE, NoteSaveParams
    )


async def upsert_repository_tool(
    ctx: Any = None, params: Any = None
) -> List[TextContent]:
    """
    Create or update repository information.
    """
    try:
        arguments = extract_arguments(ctx, params)
        validated = RepositoryData(**arguments)

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            if validated.handle:
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_REPOSITORY,
                    params=validated,
                    tree_id=tree_id,
                    handle=validated.handle,
                )
                operation = "updated"
            else:
                result = await client.make_api_call(
                    api_call=ApiCalls.POST_REPOSITORIES,
                    params=validated,
                    tree_id=tree_id,
                )
                operation = "created"

            entity_data = _extract_entity_data(result)
            formatted_response = await _format_save_response(
                client, entity_data, "repository", operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "repository save")
