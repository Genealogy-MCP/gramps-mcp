# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Delete operation for Gramps MCP tools.

Handles entity deletion; tag create/update moved to the generic upsert
(#103).
"""

import logging
from typing import Any, List

from mcp.types import TextContent

from ..client import get_client
from ..config import get_settings
from ..models.parameters.simple_params import DeleteParams
from ..overlays import item_call
from ..resource_table import ENTITY_RESOURCES
from ._compat import extract_arguments
from ._errors import McpToolError, parse_params, raise_tool_error

logger = logging.getLogger(__name__)

# Entity type -> DELETE endpoint, one per table row whose item path lists
# DELETE (#101).
# Reason: tags used to go through POST /objects/delete-by-handle/ on the
# belief that API 3.x had no DELETE /tags/{handle}. Verified against
# grampsweb 26.6.1 (webapi 3.16.0): the direct endpoint answers 200 and
# the handle is 404 afterwards, so tags take the same path as every other
# type (#90).
DELETE_API_CALLS = {
    entity: item_call(entity, "DELETE")
    for entity, row in ENTITY_RESOURCES.items()
    if "DELETE" in row.item_verbs
}


async def delete_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Delete any entity type by handle.

    Args:
        ctx: MCP context (library) or plain dict (legacy).
        params: Pydantic model (library) or None (legacy).

    Returns:
        List of TextContent with success or error message.
    """
    try:
        arguments = extract_arguments(ctx, params)
        validated = parse_params(DeleteParams, arguments)
        entity_type_str = validated.type.value

        api_call = DELETE_API_CALLS.get(entity_type_str)
        if api_call is None:
            valid = sorted(DELETE_API_CALLS.keys())
            raise McpToolError(
                f"Delete not supported for type "
                f"'{entity_type_str}'. "
                f"Valid types: {', '.join(valid)}"
            )

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = get_client()
        await client.make_api_call(
            api_call=api_call, tree_id=tree_id, handle=validated.handle
        )
        return [
            TextContent(
                type="text",
                text=(
                    f"Successfully deleted {entity_type_str} "
                    f"with handle `{validated.handle}`."
                ),
            )
        ]

    except Exception as e:
        raise_tool_error(e, "delete")
