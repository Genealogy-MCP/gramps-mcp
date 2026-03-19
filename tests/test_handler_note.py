"""Unit tests for note_handler formatting functions.

Tests format_note with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.note_handler import format_note

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

    @pytest.mark.asyncio
    async def test_note_truncation(self):
        long_text = "A" * 600
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
        assert "..." in result
        assert len(result) < 600

    @pytest.mark.asyncio
    async def test_note_empty_text(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0003",
                    "type": "General",
                    "text": {"string": ""},
                }
            }
        )
        assert await format_note(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_note_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("API error"))
        assert await format_note(client, TREE_ID, "handle123") == ""
