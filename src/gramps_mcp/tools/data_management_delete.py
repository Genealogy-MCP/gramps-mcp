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
Delete and tag operations for Gramps MCP tools.

Handles entity deletion, bulk operations, and tag creation (immutable in API 3.x).
"""

import logging
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from ..models.parameters.simple_params import DeleteParams
from ._data_helpers import _extract_entity_data
from ._errors import McpToolError, raise_tool_error

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
}

# Entity types that lack a dedicated DELETE endpoint in API 3.x and must be
# deleted via POST /objects/delete/. Maps entity type -> Gramps _class name.
# Also used as the routing predicate in delete_tool() to choose bulk vs standard DELETE.
_ENTITY_CLASS_NAMES: Dict[str, str] = {
    "tag": "Tag",
}


async def _delete_via_bulk(
    client: GrampsWebAPIClient, tree_id: str, entity_type: str, handle: str
) -> None:
    """Delete entity via POST /objects/delete/ (for types without DELETE endpoint).

    Args:
        client: Authenticated API client.
        tree_id: Tree identifier.
        entity_type: Entity type string (e.g. "tag").
        handle: Entity handle to delete.
    """
    class_name = _ENTITY_CLASS_NAMES[entity_type]
    await client.bulk_delete(
        items=[{"_class": class_name, "handle": handle}], tree_id=tree_id
    )


async def delete_tool(arguments: Dict) -> List[TextContent]:
    """
    Delete any entity type by handle.

    Args:
        arguments: Dict with 'type' (entity type) and 'handle' (entity handle).

    Returns:
        List of TextContent with success or error message.
    """
    try:
        params = DeleteParams(**arguments)
        entity_type_str = params.type.value

        api_call = DELETE_API_CALLS.get(entity_type_str)
        uses_bulk = entity_type_str in _ENTITY_CLASS_NAMES

        if not api_call and not uses_bulk:
            valid = sorted(
                list(DELETE_API_CALLS.keys()) + list(_ENTITY_CLASS_NAMES.keys())
            )
            raise McpToolError(
                f"Delete not supported for type "
                f"'{entity_type_str}'. "
                f"Valid types: {', '.join(valid)}"
            )

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            if uses_bulk:
                await _delete_via_bulk(client, tree_id, entity_type_str, params.handle)
            elif api_call is not None:
                await client.make_api_call(
                    api_call=api_call, tree_id=tree_id, handle=params.handle
                )
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Successfully deleted {entity_type_str} "
                        f"with handle `{params.handle}`."
                    ),
                )
            ]
        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "delete")


async def upsert_tag_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update a tag.

    Args:
        arguments: Dict with 'name' (required), 'color', 'priority',
            'handle' (for update).

    Returns:
        List of TextContent with formatted tag details.
    """
    from ..models.parameters.tag_params import TagSaveParams

    try:
        params = TagSaveParams(**arguments)

        if params.handle:
            raise_tool_error(
                ValueError(
                    "Tag updates are not supported in Gramps Web API 3.x. "
                    "Tags are immutable after creation. To change a tag, "
                    "delete it and create a new one."
                ),
                "tag update",
            )

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            result = await client.make_api_call(
                api_call=ApiCalls.POST_TAGS, params=params, tree_id=tree_id
            )

            entity_data = _extract_entity_data(result)
            tag_name = entity_data.get("name", "Unknown")
            tag_handle = entity_data.get("handle", "N/A")
            tag_color = entity_data.get("color", "None")
            tag_priority = entity_data.get("priority", 0)

            formatted = (
                f"Successfully created tag:\n\n"
                f"**{tag_name}** [{tag_handle}]\n"
                f"Color: {tag_color} | Priority: {tag_priority}"
            )
            return [TextContent(type="text", text=formatted)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "tag save")
