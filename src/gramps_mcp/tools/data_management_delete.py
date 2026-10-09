# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Delete and tag operations for Gramps MCP tools.

Handles entity deletion and tag create/update.
"""

import logging
from typing import Any, List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from ..models.parameters.simple_params import DeleteParams
from ._compat import extract_arguments
from ._data_helpers import _extract_entity_data
from ._errors import McpToolError, parse_params, raise_tool_error

logger = logging.getLogger(__name__)

DELETE_API_CALLS = {
    "person": ApiCalls.DELETE_PERSON,
    "family": ApiCalls.DELETE_FAMILY,
    "event": ApiCalls.DELETE_EVENT,
    "place": ApiCalls.DELETE_PLACE,
    "source": ApiCalls.DELETE_SOURCE,
    "citation": ApiCalls.DELETE_CITATION,
    "note": ApiCalls.DELETE_NOTE,
    "media": ApiCalls.DELETE_MEDIA_ITEM,
    "repository": ApiCalls.DELETE_REPOSITORY,
    # Reason: tags used to go through POST /objects/delete-by-handle/ on the
    # belief that API 3.x had no DELETE /tags/{handle}. Verified against
    # grampsweb 26.6.1 (webapi 3.16.0): the direct endpoint answers 200 and
    # the handle is 404 afterwards, so tags take the same path as every other
    # type (#90).
    "tag": ApiCalls.DELETE_TAG,
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

        client = GrampsWebAPIClient()
        try:
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
        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "delete")


async def upsert_tag_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update a tag.

    Args:
        ctx: MCP context (library) or plain dict (legacy).
        params: Pydantic model (library) or None (legacy).

    Returns:
        List of TextContent with formatted tag details.
    """
    from ..models.parameters.tag_params import TagSaveParams

    try:
        arguments = extract_arguments(ctx, params)
        validated = parse_params(TagSaveParams, arguments)

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            # Reason: PUT /tags/{handle} works on grampsweb 26.6.1 (#97). The
            # client's PUT path merges with the stored tag; tags carry no list
            # fields, so list_mode is irrelevant and scalars simply replace.
            if validated.handle:
                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_TAG,
                    params=validated,
                    tree_id=tree_id,
                    handle=validated.handle,
                )
                operation = "updated"
            else:
                result = await client.make_api_call(
                    api_call=ApiCalls.POST_TAGS, params=validated, tree_id=tree_id
                )
                operation = "created"

            entity_data = _extract_entity_data(result)
            tag_name = entity_data.get("name", "Unknown")
            tag_handle = entity_data.get("handle", "N/A")
            tag_color = entity_data.get("color", "None")
            tag_priority = entity_data.get("priority", 0)

            formatted = (
                f"Successfully {operation} tag:\n\n"
                f"**{tag_name}** [{tag_handle}]\n"
                f"Color: {tag_color} | Priority: {tag_priority}"
            )
            return [TextContent(type="text", text=formatted)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "tag save")
