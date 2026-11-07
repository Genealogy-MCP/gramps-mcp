# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Note data handler for Gramps MCP operations.

Provides clean, direct formatting of note data from handles.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Longest note text a search result or save confirmation shows; get never cuts.
MAX_NOTE_PREVIEW_LENGTH = 500

# What a shortened read ends in where the note text was cut.
ELISION = "..."

# Body placeholder for a note that exists but carries no text (issue #79).
# Returning "" here would be indistinguishable from a lookup failure.
EMPTY_NOTE_BODY = "(no text)"

# Gramps note formats; unknown values fall back to the raw int.
FORMAT_LABELS = {0: "flowed", 1: "preformatted"}


def has_elided_read(text: str, stored: str) -> bool:
    """
    Tell whether new note text was built on a shortened read of the stored text.

    Such text matches the stored text up to the cut, has the elision there,
    and has lost what the stored text held after the cut (#139). Reason: an
    ending of "..." alone proves nothing, since real notes end that way.

    Args:
        text (str): Note text about to be written.
        stored (str): Note text on the server.

    Returns:
        bool: True when writing ``text`` would delete the stored remainder.
    """
    stored = stored.strip()
    cut = len(os.path.commonprefix([text, stored]).rstrip("."))
    return (
        cut > 0
        and text.startswith(ELISION, cut)
        and not stored.startswith(ELISION, cut)
        and stored[cut:] not in text
    )


async def format_note(client, tree_id: str, handle: str) -> str:
    """
    Format note data with its whole text and type.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Note handle

    Returns:
        Formatted note string with content
    """
    return await _format_note(client, tree_id, handle, None)


async def format_note_summary(client, tree_id: str, handle: str) -> str:
    """
    Format note data for a result list, cutting long text.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Note handle

    Returns:
        Formatted note string; a cut text is reported as ``truncated: true``
        with its ``full_length``
    """
    return await _format_note(client, tree_id, handle, MAX_NOTE_PREVIEW_LENGTH)


async def _format_note(
    client, tree_id: str, handle: str, max_length: int | None
) -> str:
    """
    Fetch a note and format it, cutting text longer than ``max_length``.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Note handle
        max_length: Longest text to show, or None for the whole text

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

        cut_report = ""
        if not text:
            text = EMPTY_NOTE_BODY
        elif max_length is not None and len(text) > max_length:
            cut_report = (
                f"\ntruncated: true\nfull_length: {len(text)}"
                "\nUse get for the full text before editing this note."
            )
            text = text[: max_length - len(ELISION)] + ELISION

        header = f"{note_type} Note - {gramps_id} - [{handle}]"
        result = f"{header}\n{text}{cut_report}"

        # Format: key-presence check -- 0 (flowed) is the default and still renders
        if "format" in note_data:
            note_format = note_data["format"]
            label = FORMAT_LABELS.get(note_format, str(note_format))
            result += f"\nformat: {label}"

        return f"{result}\nprivate: {str(private).lower()}\n\n"

    except Exception as e:
        logger.warning(f"Failed to format note {handle}: {e}")
        return ""
