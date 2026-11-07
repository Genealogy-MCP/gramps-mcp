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

_LONG = "[x] Parish register\n" + "".join(
    f"[ ] Census {year} for the Rome line\n" for year in range(1800, 1830)
)
_CUT = _LONG[:497] + "..."
_REPEATING_LINE = "[ ] Census 1851 for the Rome line today\n"
_REPEATING = "Wait... list\n" + _REPEATING_LINE * 40


class _Client:
    """Records GETs and answers them with one stored note."""

    def __init__(self):
        self.gets = []

    async def call_resource(self, method, path, tree_id=None, handle=None):
        """Return the stored note, logging the handle read."""
        self.gets.append((method, handle))
        return {"text": {"_class": "StyledText", "string": _LONG}}


class TestHasElidedRead:
    """A cut read is refused wherever it was edited; other writes save."""

    @pytest.mark.parametrize(
        ("text", "stored"),
        [
            pytest.param(_CUT, _LONG, id="verbatim"),
            pytest.param(_CUT + "\nnew section", _LONG, id="appended"),
            pytest.param("New heading\n" + _CUT, _LONG, id="prepended"),
            pytest.param(_CUT.replace("[x]", "[ ]"), _LONG, id="edit-at-start"),
            pytest.param(_LONG[:496] + "Z...", _LONG, id="edit-at-the-cut"),
            pytest.param(_REPEATING[:497] + "...", _REPEATING, id="real-dots-in-read"),
            pytest.param(
                "Heading...\n" + _REPEATING[:497] + "...",
                _REPEATING,
                id="real-dots-added-to-read",
            ),
            pytest.param("A" * 497 + "...", "A" * 600, id="ending-inside-the-read"),
            pytest.param(
                "a" * 494 + "..." + "a" * 3,
                "a" * 494 + "..." + "b" * 200,
                id="stored-elision-at-the-cut",
            ),
            pytest.param(
                "He...", "He " + "was born in Rome. " * 40, id="long-note-short-read"
            ),
        ],
    )
    def test_cut_read_is_recognised(self, text, stored):
        assert has_elided_read(text, stored)

    @pytest.mark.parametrize(
        ("text", "stored"),
        [
            pytest.param(_LONG + "Checked...", _LONG, id="append"),
            pytest.param(
                "No." + _LONG[3:] + "...", _LONG[:-1] + "...", id="stored-ends-in-dots"
            ),
            pytest.param(
                _LONG[:200] + "..." + _LONG[-60:], _LONG, id="abridged-keeps-ending"
            ),
            pytest.param(
                _LONG.strip()[:-9] + "x... rome",
                _LONG.strip(),
                id="same-length-ending-edit",
            ),
            pytest.param(
                _LONG.strip().replace("[x]", "...", 1), _LONG, id="stored-whitespace"
            ),
            pytest.param(
                "Intro\n" + _REPEATING_LINE + "Wait...\n" + _REPEATING_LINE,
                _REPEATING,
                id="ending-kept-after-the-dots",
            ),
            pytest.param(
                "x" * 37 + "...", "A" * 600 + "x" * 37 + "...", id="just-the-ending"
            ),
            pytest.param(_LONG[:-5], _LONG, id="trim-without-elision"),
            pytest.param("A" * 400 + "...", "A" * 500, id="at-the-preview-limit"),
        ],
    )
    def test_other_write_is_not_a_cut_read(self, text, stored):
        assert not has_elided_read(text, stored)


class TestCheckNoteText:
    """check_note_text blocks a cut read and leaves other writes alone."""

    @pytest.mark.asyncio
    async def test_cut_read_is_refused(self):
        params = NoteSaveParams(handle="h1", text=_CUT + "\nnew section")
        with pytest.raises(McpToolError, match="Use get for the full text"):
            await check_note_text(_Client(), "tree", params)

    @pytest.mark.asyncio
    async def test_edit_with_dots_is_saved(self):
        client = _Client()
        params = NoteSaveParams(handle="h1", text=_LONG + "Unfinished...")
        await check_note_text(client, "tree", params)
        assert client.gets == [("GET", "h1")]

    @pytest.mark.asyncio
    async def test_refusal_names_the_way_through(self):
        params = NoteSaveParams(handle="h1", text=_CUT)
        with pytest.raises(McpToolError, match="allow_shortening: true"):
            await check_note_text(_Client(), "tree", params)

    @pytest.mark.asyncio
    async def test_allow_shortening_saves_without_a_get(self):
        client = _Client()
        params = NoteSaveParams(handle="h1", text=_CUT, allow_shortening=True)
        await check_note_text(client, "tree", params)
        assert client.gets == []

    def test_allow_shortening_stays_out_of_the_payload(self):
        params = NoteSaveParams(handle="h1", text="x", allow_shortening=True)
        assert "allow_shortening" not in params.to_api_payload()

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
