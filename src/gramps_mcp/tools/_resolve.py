# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Raw gramps_id -> handle resolution.

Reads handles from raw API JSON instead of formatted search text, so
sparse records whose formatters return "" still resolve (issue #78).
"""

from typing import Dict

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from ..models.parameters.base_params import BaseGetMultipleParams
from ..models.parameters.citation_params import GetCitationsParams
from ..models.parameters.event_params import EventSearchParams
from ..models.parameters.media_params import MediaSearchParams
from ..models.parameters.note_params import NotesParams
from ..models.parameters.place_params import PlaceSearchParams
from ..models.parameters.repository_params import RepositoriesParams
from ..models.parameters.source_params import SourceSearchParams
from ._errors import McpToolError

# Entity type -> (params class, list endpoint) for raw gramps_id resolution.
# Kept beside _SEARCH_TOOL_DISPATCH so a new entity type updates both.
_RESOLVE_DISPATCH: Dict[str, tuple] = {
    "person": (BaseGetMultipleParams, ApiCalls.GET_PEOPLE),
    "family": (BaseGetMultipleParams, ApiCalls.GET_FAMILIES),
    "event": (EventSearchParams, ApiCalls.GET_EVENTS),
    "place": (PlaceSearchParams, ApiCalls.GET_PLACES),
    "source": (SourceSearchParams, ApiCalls.GET_SOURCES),
    "citation": (GetCitationsParams, ApiCalls.GET_CITATIONS),
    "media": (MediaSearchParams, ApiCalls.GET_MEDIA),
    "note": (NotesParams, ApiCalls.GET_NOTES),
    "repository": (RepositoriesParams, ApiCalls.GET_REPOSITORIES),
}


async def resolve_gramps_id(entity_type: str, gramps_id: str) -> str | None:
    """
    Resolve a gramps_id to a handle from the raw API response.

    Reads `handle` directly from the JSON payload instead of parsing
    formatted display text -- formatters may return empty strings for
    sparse records (e.g. a note with no text body, issue #78), which
    would make regex extraction fail on records that exist.

    Args:
        entity_type (str): Entity type key (person, family, event, ...).
        gramps_id (str): Gramps ID to resolve (e.g. "N0042").

    Returns:
        str | None: The handle, or None when no record matches.

    Raises:
        McpToolError: If entity_type is not a known type.
    """
    dispatch = _RESOLVE_DISPATCH.get(entity_type)
    if not dispatch:
        valid_types = ", ".join(sorted(_RESOLVE_DISPATCH.keys()))
        raise McpToolError(
            f"Entity type '{entity_type}' not supported for get. "
            f"Valid types: {valid_types}"
        )
    params_class, api_call = dispatch
    params = params_class(gramps_id=gramps_id, pagesize=1)

    client = GrampsWebAPIClient()
    try:
        settings = get_settings()
        response = await client.make_api_call(
            api_call=api_call, params=params, tree_id=settings.gramps_tree_id
        )
    finally:
        await client.close()

    results = response if isinstance(response, list) else response.get("data", [])
    for item in results:
        if not isinstance(item, dict):
            continue
        obj = item.get("object", item)
        handle = obj.get("handle")
        if handle:
            return handle
    return None
