# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the note read and write paths that lost text in #139. No Docker.
"""

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.note_handler import has_elided_read
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.tools import search_basic
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.search_details import GET_HANDLERS
from src.gramps_mcp.write_hooks import check_note_text

_STORED = "alpha beta gamma delta epsilon"


class _Client:
    """Records GETs and answers them with one stored note."""

    def __init__(self):
        self.gets = []

    async def call_resource(self, method, path, tree_id=None, handle=None):
        """Return the stored note, logging the handle read."""
        self.gets.append((method, handle))
        return {"text": {"_class": "StyledText", "string": _STORED}}


_CHECKLIST = "[x] Parish register\n" + "[ ] Census 1851 for the Rome line\n" * 20
_CUT = _CHECKLIST[:497] + "..."


class TestHasElidedRead:
    """A cut read is recognised at the cut, whatever changed around it."""

    @pytest.mark.parametrize(
        "text",
        [
            _CUT,
            _CUT + "\nnew section",
            "New heading\n" + _CUT,
            _CUT.replace("[x] Parish", "[ ] Parish"),
            "A" * 497 + "...",
        ],
    )
    def test_cut_read_loses_the_tail(self, text):
        stored = "A" * 600 if text.startswith("AAA") else _CHECKLIST
        assert has_elided_read(text, stored)

    def test_preview_repeating_the_tail_does_not_hide_the_cut(self):
        preview = ("the old world and far " * 23)[:497]
        assert has_elided_read(preview + "...", preview + "ld far")

    @pytest.mark.parametrize(
        ("text", "stored"),
        [
            ("Rewritten and unfinished...", _STORED),
            ("alpha beta... gamma", "alpha beta... gamma"),
            ("alpha... beta gamma", "alpha beta gamma"),
            ("...", _STORED),
            (_STORED + " and more...", _STORED),
            ("the same line\nthe same line... kept", "the same line\nthe same line..."),
        ],
    )
    def test_text_keeping_the_stored_tail_is_not_a_cut_read(self, text, stored):
        assert not has_elided_read(text, stored)


class TestCheckNoteText:
    """check_note_text blocks a cut read and leaves other writes alone."""

    @pytest.mark.asyncio
    async def test_cut_read_is_refused(self):
        params = NoteSaveParams(handle="h1", text="alpha beta...\nnew section")
        with pytest.raises(McpToolError, match="Use get for the full text"):
            await check_note_text(_Client(), "tree", params)

    @pytest.mark.asyncio
    async def test_edit_ending_in_dots_is_saved(self):
        client = _Client()
        params = NoteSaveParams(handle="h1", text="Rewritten and unfinished...")
        await check_note_text(client, "tree", params)
        assert client.gets == [("GET", "h1")]

    @pytest.mark.parametrize(
        "params",
        [
            NoteSaveParams(handle="h1", text="plain edit"),
            NoteSaveParams(handle="h1", type="Research"),
            NoteSaveParams(text="new note...", type="General"),
        ],
    )
    @pytest.mark.asyncio
    async def test_write_that_cannot_be_a_cut_read_costs_no_get(self, params):
        client = _Client()
        await check_note_text(client, "tree", params)
        assert client.gets == []


class TestGetNoteRoute:
    """get answers with the whole note, search with the summary."""

    _NOTE = {
        "gramps_id": "N0001",
        "type": "Research",
        "text": {"string": "A" * 600},
    }

    @pytest.mark.asyncio
    async def test_get_is_uncut(self, monkeypatch):
        client = _mock_client({"GET_NOTE": self._NOTE})
        monkeypatch.setattr(search_basic, "get_client", lambda: client)
        [content] = await GET_HANDLERS["note"]({"handle": "h1"})
        assert "A" * 600 in content.text
        assert "truncated" not in content.text

    @pytest.mark.asyncio
    async def test_search_summary_is_cut(self):
        client = _mock_client({"GET_NOTE": self._NOTE})
        formatter = search_basic.FORMATTER_DISPATCH["note"]
        assert "truncated: true" in await formatter(client, "tree", "h1")
