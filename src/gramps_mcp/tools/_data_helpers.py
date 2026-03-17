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
Shared helper functions for data management tools.

Extracted to break a circular import between data_management.py,
data_management_delete.py, and data_management_media.py.
"""

import logging
from typing import Any, Dict, List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..models.api_calls import ApiCalls
from ._errors import raise_tool_error
from .search_basic import FORMATTER_DISPATCH

logger = logging.getLogger(__name__)


def _extract_entity_data(result: Any, entity_type: str | None = None) -> Any:
    """Extract entity data from API response, handling different formats."""
    if not result:
        return None

    # Handle family creation special case - find Family entry in response list
    if entity_type == "family" and isinstance(result, list) and len(result) > 1:
        family_entry = None
        for entry in result:
            if entry.get("new", {}).get("_class") == "Family":
                family_entry = entry["new"]
                break
        return family_entry if family_entry else result[0].get("new", result[0])

    # Standard case - API may return list or single object
    return (
        result[0]["new"]
        if result and isinstance(result, list) and result[0].get("new")
        else result
    )


async def _handle_crud_operation(
    params: Dict,
    entity_type: str,
    post_api_call: ApiCalls,
    put_api_call: ApiCalls,
    param_class: type,
) -> List[TextContent]:
    """Common helper for create/update operations."""
    try:
        validated_params = param_class(**params)

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            if hasattr(validated_params, "handle") and validated_params.handle:
                result = await client.make_api_call(
                    api_call=put_api_call,
                    params=validated_params,
                    tree_id=tree_id,
                    handle=validated_params.handle,
                )
                operation = "updated"
            else:
                result = await client.make_api_call(
                    api_call=post_api_call, params=validated_params, tree_id=tree_id
                )
                operation = "created"

            entity_data = _extract_entity_data(result, entity_type)
            formatted_response = await _format_save_response(
                client, entity_data, entity_type, operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, f"{entity_type} save")


async def _format_save_response(
    client: GrampsWebAPIClient,
    entity_data: Any,
    entity_type: str,
    operation: str,
    tree_id: str,
) -> str:
    """Format successful save operation response using appropriate format handler."""
    handle = entity_data.get("handle", "N/A")
    gramps_id = entity_data.get("gramps_id", "N/A")

    try:
        formatter = FORMATTER_DISPATCH.get(entity_type)
        if formatter:
            formatted_details = await formatter(client, tree_id, handle) or ""
        else:
            formatted_details = (
                f"* **{entity_type.title()} {gramps_id}** (Handle: `{handle}`)\n\n"
            )

        result = f"Successfully {operation} {entity_type}:\n\n{formatted_details}"
        return result

    except Exception as e:
        logger.warning(f"Error formatting {entity_type} details: {e}")
        # Fallback to basic formatting if handler fails
        display_name = f"{entity_type.title()} {gramps_id}"
        result = f"Successfully {operation} {entity_type}: **{display_name}**\n\n"
        result += f"**ID:** {gramps_id}\n"
        result += f"**Handle:** `{handle}`\n"
        return result
