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
        assert "private: false" in result

    @pytest.mark.asyncio
    async def test_citation_private_true(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0004",
                    "page": "",
                    "source_handle": "",
                    "date": None,
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                    "private": True,
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "private: true" in result

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

    @pytest.mark.asyncio
    async def test_citation_confidence_rendered_as_label(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0005",
                    "page": "",
                    "source_handle": "",
                    "date": None,
                    "confidence": 3,
                    "extended": {},
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "confidence: high" in result

    @pytest.mark.asyncio
    async def test_citation_confidence_zero_still_rendered(self):
        """confidence=0 is a real value (very low), not an absent field."""
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0006",
                    "page": "",
                    "source_handle": "",
                    "date": None,
                    "confidence": 0,
                    "extended": {},
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "confidence: very low" in result

    @pytest.mark.asyncio
    async def test_citation_unknown_confidence_falls_back_to_int(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0007",
                    "page": "",
                    "source_handle": "",
                    "date": None,
                    "confidence": 9,
                    "extended": {},
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "confidence: 9" in result

    @pytest.mark.asyncio
    async def test_citation_tags_rendered_by_name(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0008",
                    "page": "",
                    "source_handle": "",
                    "date": None,
                    "tag_list": ["th1", "th2"],
                    "extended": {
                        "tags": [{"name": "ToDo"}, {"name": "Verified"}],
                    },
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Tags: ToDo, Verified" in result
        assert "th1" not in result

    @pytest.mark.asyncio
    async def test_citation_empty_tag_list_omits_line(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0009",
                    "page": "",
                    "source_handle": "",
                    "date": None,
                    "tag_list": [],
                    "extended": {},
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Tags:" not in result
