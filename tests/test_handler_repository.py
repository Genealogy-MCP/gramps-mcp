"""Unit tests for repository_handler formatting functions.

Tests format_repository with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.repository_handler import format_repository

TREE_ID = "test-tree"


class TestFormatRepository:
    """Test format_repository handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        assert await format_repository(client, TREE_ID, "") == ""

    @pytest.mark.asyncio
    async def test_repo_not_found(self):
        client = _mock_client({"GET_REPOSITORY": None})
        assert await format_repository(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_repo_basic(self):
        client = _mock_client(
            {
                "GET_REPOSITORY": {
                    "gramps_id": "R0001",
                    "name": "Local Library",
                    "type": "Library",
                    "urls": [],
                    "note_list": [],
                }
            }
        )
        result = await format_repository(client, TREE_ID, "handle123")
        assert "Library" in result
        assert "Local Library" in result
        assert "R0001" in result

    @pytest.mark.asyncio
    async def test_repo_with_urls(self):
        client = _mock_client(
            {
                "GET_REPOSITORY": {
                    "gramps_id": "R0002",
                    "name": "Archives",
                    "type": "Archive",
                    "urls": [{"path": "https://example.com", "desc": "Homepage"}],
                    "note_list": [],
                }
            }
        )
        result = await format_repository(client, TREE_ID, "handle123")
        assert "https://example.com" in result
        assert "Homepage" in result

    @pytest.mark.asyncio
    async def test_repo_with_notes(self):
        client = _mock_client(
            {
                "GET_REPOSITORY": {
                    "gramps_id": "R0003",
                    "name": "Church",
                    "type": "Church",
                    "urls": [],
                    "note_list": ["note_handle_1"],
                    "extended": {
                        "notes": [{"gramps_id": "N0010", "type": "General"}],
                    },
                },
            }
        )
        result = await format_repository(client, TREE_ID, "handle123")
        assert "Attached notes" in result
        assert "N0010" in result

    @pytest.mark.asyncio
    async def test_repo_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        assert await format_repository(client, TREE_ID, "handle123") == ""
