"""Unit tests for citation_handler formatting functions.

Tests format_citation with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.citation_handler import format_citation

TREE_ID = "test-tree"


class TestFormatCitation:
    """Test format_citation handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_citation(client, TREE_ID, "")
        assert "Unknown Citation" in result

    @pytest.mark.asyncio
    async def test_citation_not_found(self):
        client = _mock_client({"GET_CITATION": None})
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Citation not found" in result

    @pytest.mark.asyncio
    async def test_citation_basic(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0001",
                    "page": "Page 42",
                    "source_handle": "src_handle",
                    "date": None,
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                },
                "GET_SOURCE": {"title": "Census 1900"},
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Census 1900" in result
        assert "Page 42" in result
        assert "C0001" in result

    @pytest.mark.asyncio
    async def test_citation_with_date(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0002",
                    "page": "",
                    "source_handle": "",
                    "date": {"dateval": [0, 0, 1900, False]},
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "1900" in result

    @pytest.mark.asyncio
    async def test_citation_with_backlinks(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0003",
                    "page": "p. 5",
                    "source_handle": "",
                    "date": None,
                    "media_list": [],
                    "note_list": [],
                    "extended": {
                        "backlinks": {
                            "person": [{"gramps_id": "I0001"}],
                            "event": [{"gramps_id": "E0001"}],
                        }
                    },
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Attached to" in result
        assert "I0001" in result
        assert "E0001" in result

    @pytest.mark.asyncio
    async def test_citation_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Error formatting citation" in result
