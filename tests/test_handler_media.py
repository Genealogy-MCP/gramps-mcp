"""Unit tests for media_handler formatting functions.

Tests format_media with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.media_handler import format_media

TREE_ID = "test-tree"


class TestFormatMedia:
    """Test format_media handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_media(client, TREE_ID, "")
        assert "No handle provided" in result

    @pytest.mark.asyncio
    async def test_media_not_found(self):
        client = _mock_client({"GET_MEDIA_ITEM": None})
        result = await format_media(client, TREE_ID, "handle123")
        assert "Media not found" in result

    @pytest.mark.asyncio
    async def test_media_with_details(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "desc": "Photo of John",
                    "mime": "image/jpeg",
                    "date": None,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "image/jpeg" in result
        assert "O0001" in result
        assert "Photo of John" in result

    @pytest.mark.asyncio
    async def test_media_with_date(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0002",
                    "desc": "Wedding photo",
                    "mime": "image/png",
                    "date": {"dateval": [15, 6, 1920, False]},
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "June" in result
        assert "1920" in result

    @pytest.mark.asyncio
    async def test_media_no_description(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0003",
                    "desc": "",
                    "mime": "",
                    "date": None,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "No description" in result
        assert "unknown type" in result

    @pytest.mark.asyncio
    async def test_media_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("timeout"))
        result = await format_media(client, TREE_ID, "handle123")
        assert "Error formatting media" in result
