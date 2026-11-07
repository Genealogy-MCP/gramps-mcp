# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for reading and rewriting a long note (#139).

get once cut note text at 500 characters, so a read, edit and write back
destroyed the rest. These tests cover the round trip against a real server.
"""

import pytest

from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.search_basic import search_tool
from src.gramps_mcp.tools.search_details import get_tool
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration

_LONG_TEXT = f"{TEST_PREFIX}research log\n" + "\n".join(
    f"[ ] check register entry {n}" for n in range(500)
)


async def _create_long_note() -> str:
    """
    Create a note far over the search preview length.

    Returns:
        str: The new note's handle.
    """
    saved = await UPSERT_HANDLERS["note"]({"text": _LONG_TEXT, "type": "Research"})
    return extract_handle(saved[0].text)


async def _read_note(handle: str) -> str:
    """
    Read a note through get.

    Args:
        handle (str): Note handle.

    Returns:
        str: The get response text.
    """
    result = await get_tool({"type": "note", "handle": handle})
    return result[0].text


@pytest.mark.asyncio
async def test_get_returns_the_whole_note():
    """Every character comes back, with no cut report."""
    text = await _read_note(await _create_long_note())
    assert _LONG_TEXT in text
    assert "truncated" not in text


@pytest.mark.asyncio
async def test_get_round_trip_keeps_the_whole_note():
    """A note edited from get output keeps its tail."""
    handle = await _create_long_note()
    edited = _LONG_TEXT + "\n[x] added line"
    await UPSERT_HANDLERS["note"]({"handle": handle, "text": edited})
    assert edited in await _read_note(handle)


@pytest.mark.asyncio
async def test_search_preview_reports_the_cut():
    """A search hit is short and says how much text it left out."""
    handle = await _create_long_note()
    result = await search_tool({"type": "note", "gql": f'handle = "{handle}"'})
    text = result[0].text
    assert f"full_length: {len(_LONG_TEXT)}" in text
    assert "truncated: true" in text
    assert _LONG_TEXT not in text


@pytest.mark.asyncio
async def test_write_back_of_a_cut_read_changes_nothing():
    """The check refuses a shortened read and the stored note survives."""
    handle = await _create_long_note()
    cut_read = _LONG_TEXT[:497] + "...\n[x] added line"
    with pytest.raises(McpToolError, match="Use get for the full text"):
        await UPSERT_HANDLERS["note"]({"handle": handle, "text": cut_read})
    assert _LONG_TEXT in await _read_note(handle)
