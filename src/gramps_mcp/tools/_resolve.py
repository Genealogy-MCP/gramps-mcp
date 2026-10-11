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

# Reason: re-exported for tests that compare the resolved endpoint against
# _resolve.ApiCalls; the endpoint itself now comes from the resource table.
from ..models.api_calls import ApiCalls as ApiCalls
from ..overlays import READ_OVERLAYS, read_route
from ._errors import McpToolError, parse_params

# Entity type -> (params class, list endpoint) for raw gramps_id resolution.
# Built from READ_OVERLAYS and the resource table, so it always matches the
# search dispatch (#101).
_RESOLVE_DISPATCH: Dict[str, tuple] = {
    entity: read_route(entity) for entity in READ_OVERLAYS
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
    params = parse_params(params_class, {"gramps_id": gramps_id, "pagesize": 1})

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
