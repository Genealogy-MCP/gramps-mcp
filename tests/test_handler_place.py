"""Unit tests for place_handler formatting functions.

Tests format_place with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.place_handler import format_place

TREE_ID = "test-tree"


class TestFormatPlace:
    """Test format_place handler."""

    @pytest.mark.asyncio
    async def test_empty_handle_inline(self):
        client = _mock_client({})
        assert await format_place(client, TREE_ID, "", inline=True) == ""

    @pytest.mark.asyncio
    async def test_empty_handle_full(self):
        client = _mock_client({})
        result = await format_place(client, TREE_ID, "", inline=False)
        assert "No handle provided" in result

    @pytest.mark.asyncio
    async def test_place_not_found_inline(self):
        client = _mock_client({"GET_PLACE": None})
        assert await format_place(client, TREE_ID, "handle123", inline=True) == ""

    @pytest.mark.asyncio
    async def test_place_not_found_full(self):
        client = _mock_client({"GET_PLACE": None})
        result = await format_place(client, TREE_ID, "handle123", inline=False)
        assert "Place not found" in result

    @pytest.mark.asyncio
    async def test_place_with_title(self):
        client = _mock_client(
            {
                "GET_PLACE": {
                    "gramps_id": "P0001",
                    "title": "Boston, MA, USA",
                    "place_type": "City",
                    "urls": [],
                    "name": {},
                    "placeref_list": [],
                }
            }
        )
        result = await format_place(client, TREE_ID, "handle123", inline=True)
        assert "Boston, MA, USA" in result

    @pytest.mark.asyncio
    async def test_place_full_format(self):
        client = _mock_client(
            {
                "GET_PLACE": {
                    "gramps_id": "P0001",
                    "title": "Boston, MA, USA",
                    "place_type": "City",
                    "urls": [{"path": "https://boston.gov", "desc": "City site"}],
                    "name": {},
                    "placeref_list": [],
                }
            }
        )
        result = await format_place(client, TREE_ID, "handle123", inline=False)
        assert "City" in result
        assert "P0001" in result
        assert "https://boston.gov" in result

    @pytest.mark.asyncio
    async def test_place_hierarchy_from_name(self):
        # Place with no title but name + parent
        client = _mock_client(
            {
                "GET_PLACE": [
                    {
                        "gramps_id": "P0002",
                        "title": "",
                        "place_type": "City",
                        "urls": [],
                        "name": {"value": "Springfield"},
                        "placeref_list": [{"ref": "parent_handle"}],
                    },
                    {
                        "title": "Illinois, USA",
                        "name": {"value": "Illinois"},
                        "placeref_list": [],
                    },
                ]
            }
        )
        result = await format_place(client, TREE_ID, "handle123", inline=True)
        assert "Springfield" in result

    @pytest.mark.asyncio
    async def test_place_api_error_inline(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        assert await format_place(client, TREE_ID, "handle123", inline=True) == ""

    @pytest.mark.asyncio
    async def test_place_api_error_full(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_place(client, TREE_ID, "handle123", inline=False)
        assert result == ""

    @pytest.mark.asyncio
    async def test_place_format_error_non_inline_returns_empty(self):
        """Broken place record (e.g. orphaned parent handle) returns empty string."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("Record not found"))
        result = await format_place(client, TREE_ID, "broken_handle", inline=False)
        assert result == ""
        assert "error" not in result.lower()
