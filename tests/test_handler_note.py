"""Unit tests for note_handler formatting functions.

Tests format_note with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.note_handler import (
    EMPTY_NOTE_BODY,
    format_note,
    format_note_summary,
    has_elided_read,
)

TREE_ID = "test-tree"


class TestFormatNote:
    """Test format_note handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        assert await format_note(client, TREE_ID, "") == ""

    @pytest.mark.asyncio
    async def test_note_not_found(self):
        client = _mock_client({"GET_NOTE": None})
        assert await format_note(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_note_with_content(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0001",
                    "type": "General",
                    "text": {"string": "This is a test note."},
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "General Note" in result
        assert "N0001" in result
        assert "This is a test note." in result
        assert "private: false" in result

    @pytest.mark.asyncio
    async def test_note_private_true(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0004",
                    "type": "General",
                    "text": {"string": "Secret note."},
                    "private": True,
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "private: true" in result

    @pytest.mark.asyncio
    async def test_long_note_text_is_returned_whole(self):
        """get must hand back every character, or a write-back destroys it (#139)."""
        long_text = "A" * 12000 + " the end"
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0002",
                    "type": "Research",
                    "text": {"string": long_text},
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert result == (
            f"Research Note - N0002 - [handle123]\n{long_text}\nprivate: false\n\n"
        )

    @pytest.mark.asyncio
    async def test_note_empty_text_renders_stub(self):
        """An existing note with an empty body still identifies itself (#79)."""
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0003",
                    "type": "General",
                    "text": {"string": ""},
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "General Note" in result
        assert "N0003" in result
        assert "handle123" in result
        assert EMPTY_NOTE_BODY in result

    @pytest.mark.asyncio
    async def test_note_missing_text_key_renders_stub(self):
        client = _mock_client({"GET_NOTE": {"gramps_id": "N0005", "type": "Research"}})
        result = await format_note(client, TREE_ID, "handle123")
        assert EMPTY_NOTE_BODY in result

    @pytest.mark.asyncio
    async def test_note_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("API error"))
        assert await format_note(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_note_format_flowed_rendered(self):
        """format=0 (flowed) is the default and still renders."""
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0006",
                    "type": "General",
                    "text": {"string": "plain note"},
                    "format": 0,
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "format: flowed" in result

    @pytest.mark.asyncio
    async def test_note_format_preformatted_rendered(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0007",
                    "type": "General",
                    "text": {"string": "  spaced\n  note"},
                    "format": 1,
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "format: preformatted" in result

    @pytest.mark.asyncio
    async def test_note_unknown_format_falls_back_to_int(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0008",
                    "type": "General",
                    "text": {"string": "note"},
                    "format": 7,
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "format: 7" in result


class TestFormatNoteSummary:
    """Search results cut long notes and say so in metadata (#139)."""

    @pytest.mark.asyncio
    async def test_long_note_reports_the_cut(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0002",
                    "type": "Research",
                    "text": {"string": "A" * 600},
                }
            }
        )
        assert await format_note_summary(client, TREE_ID, "handle123") == (
            "Research Note - N0002 - [handle123]\n"
            f"{'A' * 497}...\n"
            "truncated: true\n"
            "full_length: 600\n"
            "Use get for the full text before editing this note.\n"
            "private: false\n\n"
        )

    @pytest.mark.asyncio
    async def test_note_at_the_limit_is_not_cut(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0002",
                    "type": "Research",
                    "text": {"string": "A" * 500},
                }
            }
        )
        assert await format_note_summary(client, TREE_ID, "handle123") == (
            f"Research Note - N0002 - [handle123]\n{'A' * 500}\nprivate: false\n\n"
        )


class TestHasElidedRead:
    """Tell a write built from a cut read from an edit that uses dots (#139)."""

    @pytest.mark.parametrize(
        ("text", "stored", "expected"),
        [
            ("alpha beta...", "alpha beta gamma delta", True),
            ("alpha beta...\nnew section", "alpha beta gamma delta", True),
            ("alpha...", "alpha.beta gamma", True),
            ("alpha....", "alpha.beta gamma", True),
            ("alpha beta...", "alpha beta", False),
            ("alpha beta... gamma", "alpha beta gamma", False),
            ("Maybe...tomorrow", "Maybe...later on", False),
            ("Maybe... and more", "Maybe...", False),
            ("something else...", "alpha beta gamma", False),
            ("...", "", False),
            ("...rewritten from scratch", "alpha beta gamma", False),
            ("alpha beta gamma", "alpha beta gamma delta", False),
        ],
    )
    def test_cases(self, text, stored, expected):
        assert has_elided_read(text, stored) is expected
