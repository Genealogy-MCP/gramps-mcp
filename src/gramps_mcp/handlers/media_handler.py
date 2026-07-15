# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Media data handler for Gramps MCP operations.

Provides clean, direct formatting of media data from handles.
"""

import logging

from ..models.api_calls import ApiCalls
from .date_handler import format_date

logger = logging.getLogger(__name__)

_PATH_SUPPRESSED = "[non-relative path suppressed]"


def render_media_path(path: str) -> str:
    """
    Render a media path safely for audit output.

    Reason: MCP-19 forbids leaking server filesystem locations. Absolute paths,
    home-directory (`~`) references, and parent-directory traversal could
    disclose host structure, so only tree-relative paths are shown verbatim;
    anything else is suppressed.

    Args:
        path (str): Stored media path (may be empty).

    Returns:
        str: The path verbatim when relative (including empty), otherwise the
            suppression marker.
    """
    if not path:
        return path
    # Reason: inspect the trimmed value so leading whitespace cannot shift an
    # absolute marker (e.g. "  /etc/passwd") past the positional checks below.
    probe = path.strip()
    if not probe:
        return path
    if probe[0] in ("/", "\\", "~"):
        return _PATH_SUPPRESSED
    # Windows drive letter, e.g. "C:\\..."
    if len(probe) >= 2 and probe[1] == ":":
        return _PATH_SUPPRESSED
    segments = probe.replace("\\", "/").split("/")
    if ".." in segments:
        return _PATH_SUPPRESSED
    return path


async def format_media(client, tree_id: str, handle: str) -> str:
    """
    Format media data with description, path, and type details.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Media handle

    Returns:
        Formatted media string with details
    """
    if not handle:
        return "**Unknown Media**\n  No handle provided\n\n"

    try:
        media_data = await client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM, tree_id=tree_id, handle=handle
        )
        if not media_data:
            return f"**Media {handle}**\n  Media not found\n\n"

        gramps_id = media_data.get("gramps_id", "N/A")
        desc = media_data.get("desc", "").strip()
        mime = media_data.get("mime", "").strip()
        date_info = media_data.get("date", {})
        path = media_data.get("path", "") or ""
        checksum = media_data.get("checksum", "") or ""
        private = bool(media_data.get("private", False))

        # Format description
        formatted_desc = desc if desc else "No description"

        # Format date if present
        formatted_date = ""
        if date_info and isinstance(date_info, dict):
            date_result = format_date(date_info)
            if date_result != "date unknown":
                formatted_date = f" - {date_result}"

        # New format: file type - gramps id - [handle] \n desc - date
        file_type = mime if mime else "unknown type"
        first_line = f"{file_type} - {gramps_id} - [{handle}]"
        second_line = f"{formatted_desc}{formatted_date}"

        audit_lines = (
            f"  Path: {render_media_path(path)}\n"
            f"  Checksum: {checksum}\n"
            f"  Private: {'true' if private else 'false'}"
        )

        return f"{first_line}\n{second_line}\n{audit_lines}\n\n"

    except Exception as e:
        logger.warning(f"Failed to format media {handle}: {e}")
        return f"**Media {handle}**\n  Error formatting media: {str(e)}\n\n"
