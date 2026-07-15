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
        text = note_data.get("text", {}).get("string")
        private = note_data.get("private", False)

        if not text:
            return ""

        # Clean up text - remove excessive whitespace but preserve paragraph breaks
        text = text.strip()

        # Truncate if too long
        if len(text) > MAX_NOTE_LENGTH:
            text = text[: MAX_NOTE_LENGTH - 3] + "..."

        header = f"{note_type} Note - {gramps_id} - [{handle}]"
        return f"{header}\n{text}\nprivate: {str(private).lower()}\n\n"

    except Exception as e:
        logger.warning(f"Failed to format note {handle}: {e}")
        return ""
