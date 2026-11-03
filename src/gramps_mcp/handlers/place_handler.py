# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Place data handler for Gramps MCP operations.

Provides clean, direct formatting of place data from handles.
"""

import logging

from ..models.api_calls import ApiCalls
from ..models.parameters.base_params import BaseGetSingleParams

logger = logging.getLogger(__name__)


async def format_place(client, tree_id: str, handle: str, inline: bool = False) -> str:
    """
    Format place data with full hierarchy and details.

    Args:
        client: Gramps API client instance
        tree_id (str): Family tree identifier
        handle (str): Place handle
        inline (bool, optional): If True, return just the hierarchy for inline use

    Returns:
        str: Formatted place string with hierarchy (and details if not inline)
    """
    if not handle:
        return "" if inline else "• **Place**\n  No handle provided\n\n"

    try:
        place_data = await client.make_api_call(
            api_call=ApiCalls.GET_PLACE,
            tree_id=tree_id,
            handle=handle,
            params=BaseGetSingleParams.model_validate({"profile": "self"}),
        )
        if not place_data:
            return "" if inline else f"• **Place {handle}**\n  Place not found\n\n"

        place_hierarchy = _build_place_hierarchy(place_data)

        # For inline use, just return the hierarchy
        if inline:
            return place_hierarchy if place_hierarchy else ""

        # For search results, return new format
        gramps_id = place_data.get("gramps_id", "")
        place_type = place_data.get("place_type", "")
        urls = place_data.get("urls", [])

        # First line: type: title (full hierarchy) - gramps_id - [handle]
        title = place_hierarchy if place_hierarchy else ""
        first_line = f"{place_type}: {title} - {gramps_id} - [{handle}]"
        result = first_line

        # Second line: url path - url desc (if URLs present)
        for url in urls:
            if isinstance(url, dict):
                url_path = url.get("path", "")
                url_desc = url.get("desc", "")
                if url_path:
                    url_line = url_path
                    if url_desc:
                        url_line += f" - {url_desc}"
                    result += f"\n{url_line}"

        private = place_data.get("private", False)
        result += f"\nprivate: {str(private).lower()}"

        return result + "\n\n"

    except Exception as e:
        logger.warning(f"Failed to format place {handle}: {e}")
        return ""


def _build_place_hierarchy(place_data: dict) -> str:
    """
    Build the "place, enclosing, ..., country" string from one place record.

    Args:
        place_data (dict): Place record fetched with ``profile=self``.

    Returns:
        str: The place title if set, otherwise its name followed by the names
        in ``profile.parent_places``.
    """
    title = place_data.get("title", "")
    if title:
        return title

    # Reason: Gramps Web walks the enclosing chain server side and stops on a
    # revisited handle, so a placeref cycle yields a finite list and the
    # hierarchy costs one request at any depth (#122). Its walk never marks
    # the starting place visited, so A -> B -> A comes back as [B, A]; stop at
    # the first place already named.
    profile = place_data.get("profile") or {}
    seen = {place_data.get("gramps_id")}
    names = [place_data.get("name", {}).get("value", "")]
    for parent in profile.get("parent_places", []):
        # Reason: Gramps allows an empty gramps_id, which says nothing about
        # identity, so only a non-empty repeat counts as a cycle.
        parent_id = parent.get("gramps_id")
        if parent_id and parent_id in seen:
            logger.warning(
                f"Placeref cycle at {parent_id} above place "
                f"{place_data.get('gramps_id')}; hierarchy truncated"
            )
            break
        seen.add(parent_id)
        names.append(parent.get("name", ""))
    return ", ".join(name for name in names if name)
