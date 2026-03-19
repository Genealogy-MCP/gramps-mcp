"""Unit tests for source_handler formatting functions.

Tests format_source with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.source_handler import format_source

TREE_ID = "test-tree"


class TestFormatSource:
    """Test format_source handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_source(client, TREE_ID, "")
        assert "Unknown Source" in result

    @pytest.mark.asyncio
    async def test_source_not_found(self):
        client = _mock_client({"GET_SOURCE": None})
        result = await format_source(client, TREE_ID, "handle123")
        assert "Source not found" in result

    @pytest.mark.asyncio
    async def test_source_basic(self):
        client = _mock_client(
            {
                "GET_SOURCE": {
                    "gramps_id": "S0001",
                    "title": "Marriage Register",
                    "author": "St. Mary's",
                    "pubinfo": "Original manuscript",
                    "note_list": [],
                    "reporef_list": [],
                    "media_list": [],
                }
            }
        )
        result = await format_source(client, TREE_ID, "handle123")
        assert "Marriage Register" in result
        assert "S0001" in result
        assert "St. Mary's" in result
        assert "Original manuscript" in result

    @pytest.mark.asyncio
    async def test_source_no_author(self):
        client = _mock_client(
            {
                "GET_SOURCE": {
                    "gramps_id": "S0002",
                    "title": "Census 1900",
                    "author": "",
                    "pubinfo": "",
                    "note_list": [],
                    "reporef_list": [],
                    "media_list": [],
                }
            }
        )
        result = await format_source(client, TREE_ID, "handle123")
        assert "Census 1900" in result
        # No second line since no author or pubinfo
        assert result.count("\n") >= 1

    @pytest.mark.asyncio
    async def test_source_with_repo(self):
        client = _mock_client(
            {
                "GET_SOURCE": {
                    "gramps_id": "S0003",
                    "title": "Church Records",
                    "author": "",
                    "pubinfo": "",
                    "note_list": [],
                    "reporef_list": [{"ref": "repo_handle_1"}],
                    "media_list": [],
                    "extended": {
                        "repositories": [
                            {"name": "National Archives", "gramps_id": "R0001"}
                        ],
                        "media": [],
                        "notes": [],
                    },
                },
            }
        )
        result = await format_source(client, TREE_ID, "handle123")
        assert "National Archives" in result
        assert "R0001" in result

    @pytest.mark.asyncio
    async def test_source_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("network error"))
        result = await format_source(client, TREE_ID, "handle123")
        assert "Error formatting source" in result
