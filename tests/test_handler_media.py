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

    @pytest.mark.asyncio
    async def test_audit_fields_present(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "desc": "Photo of John",
                    "mime": "image/jpeg",
                    "date": None,
                    "path": "images/photo.jpg",
                    "checksum": "abc123def",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "path" in result.lower()
        assert "checksum" in result.lower()
        assert "private" in result.lower()
        assert "abc123def" in result

    @pytest.mark.asyncio
    async def test_private_renders_true(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "images/photo.jpg",
                    "checksum": "x",
                    "private": True,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "Private: true" in result

    @pytest.mark.asyncio
    async def test_private_renders_false(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "images/photo.jpg",
                    "checksum": "x",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "Private: false" in result

    @pytest.mark.asyncio
    async def test_audit_fields_present_when_empty(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "",
                    "checksum": "",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "Path:" in result
        assert "Checksum:" in result
        assert "Private: false" in result

    @pytest.mark.asyncio
    async def test_relative_path_shown_verbatim(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "images/photo.jpg",
                    "checksum": "x",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "images/photo.jpg" in result
        assert "suppressed" not in result

    @pytest.mark.asyncio
    async def test_absolute_path_suppressed(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "/etc/passwd",
                    "checksum": "x",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "/etc/passwd" not in result
        assert "[non-relative path suppressed]" in result

    @pytest.mark.asyncio
    async def test_parent_traversal_path_suppressed(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "images/../../secret",
                    "checksum": "x",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "secret" not in result
        assert "[non-relative path suppressed]" in result

    @pytest.mark.asyncio
    async def test_whitespace_padded_absolute_path_suppressed(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "  /etc/passwd",
                    "checksum": "x",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "/etc/passwd" not in result
        assert "[non-relative path suppressed]" in result

    @pytest.mark.asyncio
    async def test_home_directory_path_suppressed(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "mime": "image/jpeg",
                    "path": "~/secret",
                    "checksum": "x",
                    "private": False,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "secret" not in result
        assert "[non-relative path suppressed]" in result
