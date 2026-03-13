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
Utility functions for gramps_mcp.
"""

import logging
from typing import Union

from markdownify import markdownify as md

from .models.api_calls import ApiCalls

logger = logging.getLogger(__name__)

# Gramps internal numeric class codes (from gramps/gen/db/dbconst.py).
# Transaction history may return these instead of string names.
_GRAMPS_CLASS_CODES: dict[int, str] = {
    0: "Person",
    1: "Family",
    2: "Source",
    3: "Event",
    4: "Media",
    5: "Place",
    6: "Repository",
    7: "Note",
    8: "Tag",
    9: "Citation",
}

# Dispatch dict mapping lowercase class name to the GET ApiCall.
_CLASS_TO_API_CALL: dict[str, ApiCalls] = {
    "person": ApiCalls.GET_PERSON,
    "family": ApiCalls.GET_FAMILY,
    "event": ApiCalls.GET_EVENT,
    "place": ApiCalls.GET_PLACE,
    "source": ApiCalls.GET_SOURCE,
    "citation": ApiCalls.GET_CITATION,
    "media": ApiCalls.GET_MEDIA_ITEM,
    "note": ApiCalls.GET_NOTE,
    "repository": ApiCalls.GET_REPOSITORY,
}


def normalize_obj_class(obj_class: Union[str, int]) -> str:
    """
    Convert a Gramps object class to its canonical string name.

    Handles numeric codes from transaction history and string digit values.

    Args:
        obj_class: Class name (str) or numeric code (int).

    Returns:
        Canonical class name (e.g. "Person", "Place").
    """
    if isinstance(obj_class, int):
        return _GRAMPS_CLASS_CODES.get(obj_class, f"Unknown({obj_class})")

    # Handle string digits like "5" → "Place"
    if isinstance(obj_class, str) and obj_class.isdigit():
        return _GRAMPS_CLASS_CODES.get(int(obj_class), f"Unknown({obj_class})")

    return str(obj_class)


def html_to_markdown(html: str) -> str:
    """
    Convert HTML content to Markdown format.

    Args:
        html: HTML string to convert

    Returns:
        Markdown formatted string
    """
    if not html or not html.strip():
        return ""

    return md(html, heading_style="ATX")


async def get_gramps_id_from_handle(
    client, obj_class: Union[str, int], obj_handle: str, tree_id: str
) -> str:
    """
    Convert an object handle to its gramps_id using the appropriate API call.

    Args:
        client: GrampsWebAPIClient instance
        obj_class: Object class/type (e.g., "Person", "Family", 5)
        obj_handle: Object handle to convert
        tree_id: Tree identifier

    Returns:
        Gramps ID if found, otherwise the original handle
    """
    try:
        class_name = normalize_obj_class(obj_class)
        api_call = _CLASS_TO_API_CALL.get(class_name.lower())

        if api_call is None:
            return obj_handle

        obj_info = await client.make_api_call(
            api_call=api_call,
            params=None,
            tree_id=tree_id,
            handle=obj_handle,
        )

        if obj_info and "gramps_id" in obj_info:
            return obj_info["gramps_id"]
        return obj_handle

    except Exception as e:
        logger.warning(f"Failed to resolve handle {obj_handle} to gramps_id: {e}")
        return obj_handle
