"""
Unit tests for download_media_tool handler.

Tests validate path security, identifier resolution, error handling,
and successful download flow — all with mocked API calls (no Docker).
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.data_management_media import download_media_tool


def _mock_settings():
    """Return a mock settings object."""
    return type("Settings", (), {"gramps_tree_id": "tree1"})()


# Shared patch targets in data_management_media module
_PATCH_SETTINGS = patch(
    "src.gramps_mcp.tools.data_management_media.get_settings",
    return_value=_mock_settings(),
)
_PATCH_CLIENT = patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
_PATCH_MEDIA = patch("src.gramps_mcp.tools.data_management_media.MediaClient")


class TestDownloadMediaValidation:
    """Test input validation before any API call."""

    @pytest.mark.asyncio
    async def test_requires_identifier(self):
        """No handle or gramps_id raises McpToolError."""
        with pytest.raises(McpToolError, match="handle.*gramps_id"):
            await download_media_tool({"destination": "/tmp/test.jpg"})

    @pytest.mark.asyncio
    async def test_requires_absolute_path(self):
        """Relative path raises McpToolError."""
        with pytest.raises(McpToolError, match="absolute"):
            await download_media_tool(
                {"handle": "abcdefgh", "destination": "relative/path.jpg"}
            )

    @pytest.mark.asyncio
    async def test_rejects_path_traversal(self, tmp_path):
        """Path with '..' components raises McpToolError."""
        traversal_path = str(tmp_path / ".." / "escaped.jpg")
        with pytest.raises(McpToolError, match="traversal"):
            await download_media_tool(
                {"handle": "abcdefgh", "destination": traversal_path}
            )

    @pytest.mark.asyncio
    async def test_parent_directory_not_found(self):
        """Non-existent parent directory raises McpToolError."""
        with pytest.raises(McpToolError, match="directory.*does not exist"):
            await download_media_tool(
                {"handle": "abcdefgh", "destination": "/nonexistent/dir/file.jpg"}
            )

    @pytest.mark.asyncio
    async def test_rejects_directory_as_destination(self, tmp_path):
        """Existing directory as destination raises McpToolError."""
        with pytest.raises(McpToolError, match="directory.*not a file"):
            await download_media_tool(
                {"handle": "abcdefgh", "destination": str(tmp_path)}
            )


class TestDownloadMediaSuccess:
    """Test successful download flows with mocked API."""

    @pytest.mark.asyncio
    @_PATCH_MEDIA
    @_PATCH_CLIENT
    @_PATCH_SETTINGS
    async def test_download_with_handle(
        self, _settings, mock_client_cls, mock_media_cls, tmp_path
    ):
        """Download by handle writes file and returns metadata."""
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={
                "handle": "m1handle1",
                "gramps_id": "O0001",
                "desc": "Birth certificate",
                "mime": "image/jpeg",
            }
        )
        mock_client_cls.return_value = client_inst

        media_inst = AsyncMock()
        media_inst.download_media_file = AsyncMock(
            return_value=(b"fake jpeg content", "image/jpeg")
        )
        mock_media_cls.return_value = media_inst

        dest = str(tmp_path / "downloaded.jpg")
        result = await download_media_tool(
            {"handle": "m1handle1", "destination": dest}
        )

        assert isinstance(result[0], TextContent)
        assert os.path.isfile(dest)
        with open(dest, "rb") as f:
            assert f.read() == b"fake jpeg content"

        text = result[0].text
        assert "m1handle1" in text
        assert "image/jpeg" in text

    @pytest.mark.asyncio
    @_PATCH_MEDIA
    @_PATCH_CLIENT
    @_PATCH_SETTINGS
    async def test_download_with_gramps_id(
        self, _settings, mock_client_cls, mock_media_cls, tmp_path
    ):
        """Download by gramps_id resolves handle then downloads."""
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        # First call: resolve gramps_id -> list with one result
        # Second call: get media metadata
        client_inst.make_api_call = AsyncMock(
            side_effect=[
                [{"handle": "resolved1"}],
                {
                    "handle": "resolved1",
                    "gramps_id": "O0042",
                    "desc": "Photo",
                    "mime": "image/png",
                },
            ]
        )
        mock_client_cls.return_value = client_inst

        media_inst = AsyncMock()
        media_inst.download_media_file = AsyncMock(
            return_value=(b"png bytes", "image/png")
        )
        mock_media_cls.return_value = media_inst

        dest = str(tmp_path / "photo.png")
        result = await download_media_tool(
            {"gramps_id": "O0042", "destination": dest}
        )

        assert os.path.isfile(dest)
        text = result[0].text
        assert "O0042" in text or "resolved1" in text

    @pytest.mark.asyncio
    @_PATCH_MEDIA
    @_PATCH_CLIENT
    @_PATCH_SETTINGS
    async def test_gramps_id_not_found(
        self, _settings, mock_client_cls, mock_media_cls
    ):
        """gramps_id with no results raises McpToolError."""
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value=[])
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError, match="No media.*O9999"):
            await download_media_tool(
                {"gramps_id": "O9999", "destination": "/tmp/test.jpg"}
            )

    @pytest.mark.asyncio
    @_PATCH_MEDIA
    @_PATCH_CLIENT
    @_PATCH_SETTINGS
    async def test_api_error_wraps_as_mcp_error(
        self, _settings, mock_client_cls, mock_media_cls, tmp_path
    ):
        """API errors during download are wrapped as McpToolError."""
        from src.gramps_mcp.client import GrampsAPIError

        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={
                "handle": "m1handle1",
                "gramps_id": "O0001",
                "desc": "Test",
                "mime": "image/jpeg",
            }
        )
        mock_client_cls.return_value = client_inst

        media_inst = AsyncMock()
        media_inst.download_media_file = AsyncMock(
            side_effect=GrampsAPIError("Not found on API")
        )
        mock_media_cls.return_value = media_inst

        dest = str(tmp_path / "fail.jpg")
        with pytest.raises(McpToolError, match="Not found on API"):
            await download_media_tool(
                {"handle": "m1handle1", "destination": dest}
            )
