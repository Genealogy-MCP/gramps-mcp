# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Note data handler for Gramps MCP operations.

Provides clean, direct formatting of note data from handles.
"""

import logging

logger = logging.getLogger(__name__)

# Constants
MAX_NOTE_LENGTH = 500

# Body placeholder for a note that exists but carries no text (issue #79).
# Returning "" here would be indistinguishable from a lookup failure.
EMPTY_NOTE_BODY = "(no text)"

# Gramps note formats; unknown values fall back to the raw int.
FORMAT_LABELS = {0: "flowed", 1: "preformatted"}


async def format_note(client, tree_id: str, handle: str) -> str:
    """
    Format note data with text content and type.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Note handle

    Returns:
        Formatted note string with content
    """
    if not handle:
        return ""

    try:
        from ..models.api_calls import ApiCalls

        note_data = await client.make_api_call(
            api_call=ApiCalls.GET_NOTE, tree_id=tree_id, handle=handle
        )
        if not note_data:
            return ""

        gramps_id = note_data.get("gramps_id")
        note_type = note_data.get("type")
        text = (note_data.get("text") or {}).get("string") or ""
        private = note_data.get("private", False)

        # Clean up text - remove excessive whitespace but preserve paragraph breaks
        text = text.strip()

        if not text:
            text = EMPTY_NOTE_BODY
        elif len(text) > MAX_NOTE_LENGTH:
            text = text[: MAX_NOTE_LENGTH - 3] + "..."

        header = f"{note_type} Note - {gramps_id} - [{handle}]"
        result = f"{header}\n{text}"

        # Format: key-presence check -- 0 (flowed) is the default and still renders
        if "format" in note_data:
            note_format = note_data["format"]
            label = FORMAT_LABELS.get(note_format, str(note_format))
            result += f"\nformat: {label}"

        return f"{result}\nprivate: {str(private).lower()}\n\n"

    except Exception as e:
        logger.warning(f"Failed to format note {handle}: {e}")
        return ""
