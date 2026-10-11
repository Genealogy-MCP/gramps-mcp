# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for the generic table-driven upsert (#102).

Run against the Docker test instance only. Cover the fields the table
gained through ``resource_policy.FIELD_ADDITIONS`` (note note_list and
attribute_list), the PUT merge path and the citation nudge on create.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.tools import upsert_event_tool, upsert_note_tool

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

    async def test_note_lists_round_trip_and_merge(self):
        """note_list and attribute_list persist; a PUT merges by default."""
        first = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}linked note A", "type": "General"}
        )
        linked_a = extract_handle(first[0].text)
        second = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}linked note B", "type": "General"}
        )
        linked_b = extract_handle(second[0].text)

        created = await upsert_note_tool(
            {
                "text": f"{TEST_PREFIX}note with lists",
                "type": "General",
                "note_list": [linked_a],
                "attribute_list": [{"type": "Nickname", "value": "probe"}],
            }
        )
        handle = extract_handle(created[0].text)
        await upsert_note_tool({"handle": handle, "note_list": [linked_b]})

        stored = await _get("notes/{handle}", handle)
        assert (
            stored["note_list"],
            [a["value"] for a in stored["attribute_list"]],
            stored["text"]["string"],
        ) == ([linked_a, linked_b], ["probe"], f"{TEST_PREFIX}note with lists")

    async def test_event_create_without_citation_nudges(self):
        """An uncited event create carries the unchanged citation nudge."""
        result = await upsert_event_tool(
            {"type": "Birth", "description": f"{TEST_PREFIX}uncited birth"}
        )
        assert result[0].text.startswith("Successfully created event:") and (
            result[0].text.endswith(
                "\n> Note: created without a citation. "
                "Consider adding a source to support this record.\n"
            )
        )
