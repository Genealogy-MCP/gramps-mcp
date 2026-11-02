# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for the generic table-driven upsert (#102).

Run against the Docker test instance only. Cover a list field round trip
through the PUT merge path and the citation nudge on create.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _get(path, handle):
    """
    Fetch one stored record through the table path.

    Args:
        path (str): Item path template, e.g. ``notes/{handle}``.
        handle (str): Record handle.

    Returns:
        dict: The stored record.
    """
    client = GrampsWebAPIClient()
    try:
        return await client.call_resource(
            "GET", path, tree_id=get_settings().gramps_tree_id, handle=handle
        )
    finally:
        await client.close()


class TestGenericUpsertRoundTrip:
    """Fields written by the generic upsert come back from the server."""

    async def test_note_tag_list_round_trip_and_merge(self):
        """A note's tag_list persists and a PUT merges it by default."""
        tag_a = await UPSERT_HANDLERS["tag"]({"name": f"{TEST_PREFIX}NoteTagA"})
        tag_b = await UPSERT_HANDLERS["tag"]({"name": f"{TEST_PREFIX}NoteTagB"})
        handle_a = extract_handle(tag_a[0].text)
        handle_b = extract_handle(tag_b[0].text)

        created = await UPSERT_HANDLERS["note"](
            {
                "text": f"{TEST_PREFIX}note with tags",
                "type": "General",
                "tag_list": [handle_a],
            }
        )
        handle = extract_handle(created[0].text)
        await UPSERT_HANDLERS["note"]({"handle": handle, "tag_list": [handle_b]})

        stored = await _get("notes/{handle}", handle)
        assert (stored["tag_list"], stored["text"]["string"]) == (
            [handle_a, handle_b],
            f"{TEST_PREFIX}note with tags",
        )

    async def test_event_create_without_citation_nudges(self):
        """An uncited event create carries the unchanged citation nudge."""
        result = await UPSERT_HANDLERS["event"](
            {"type": "Birth", "description": f"{TEST_PREFIX}uncited birth"}
        )
        assert result[0].text.startswith("Successfully created event:") and (
            result[0].text.endswith(
                "\n> Note: created without a citation. "
                "Consider adding a source to support this record.\n"
            )
        )
