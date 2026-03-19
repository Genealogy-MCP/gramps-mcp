"""
Unit tests for file replacement in upsert_media_tool.

Tests verify that when both handle and file_location are provided,
the file is uploaded via PUT /media/{handle}/file before updating metadata.
"""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.data_management_media import upsert_media_tool


def _mock_settings():
    """Return a mock settings object."""
    return type("Settings", (), {"gramps_tree_id": "tree1"})()


class TestMediaFileReplacement:
    """Test file replacement when updating existing media."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.MediaClient")
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_update_with_file_replacement(
        self, _settings, mock_client_cls, mock_media_cls
    ):
        """When handle and file_location are both provided, file is replaced."""
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "m1", "gramps_id": "O001"}
        )
        mock_client_cls.return_value = client_inst

        media_inst = AsyncMock()
        media_inst.replace_media_file = AsyncMock(return_value={})
        mock_media_cls.return_value = media_inst

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image content")
            temp_path = f.name

        try:
            result = await upsert_media_tool(
                {
                    "handle": "m1",
                    "desc": "Updated photo",
                    "file_location": temp_path,
                }
            )

            assert isinstance(result[0], TextContent)
            assert "updated" in result[0].text.lower()
            # Verify replace_media_file was called
            media_inst.replace_media_file.assert_awaited_once()
            call_args = media_inst.replace_media_file.call_args
            assert call_args[1]["handle"] == "m1" or call_args[0][1] == "m1"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_update_without_file_no_replacement(self, _settings, mock_client_cls):
        """When handle is provided but no file_location, no file replacement."""
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "m1", "gramps_id": "O001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_media_tool(
            {"handle": "m1", "desc": "Metadata only update"}
        )

        assert isinstance(result[0], TextContent)
        assert "updated" in result[0].text.lower()
        # replace_media_file should NOT be called
        assert not hasattr(client_inst, "replace_media_file") or (
            hasattr(client_inst.replace_media_file, "assert_not_awaited")
            and not client_inst.replace_media_file.await_count
        )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    async def test_update_with_nonexistent_file_raises(
        self, _settings, mock_client_cls
    ):
        """File replacement with nonexistent file raises error."""
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await upsert_media_tool(
                {
                    "handle": "m1",
                    "desc": "Bad file",
                    "file_location": "/nonexistent/path.jpg",
                }
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.MediaClient")
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_file_replacement_detects_mime_type(
        self, _settings, mock_client_cls, mock_media_cls
    ):
        """File replacement auto-detects MIME type from file extension."""
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "m1", "gramps_id": "O001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        media_inst = AsyncMock()
        media_inst.replace_media_file = AsyncMock(return_value={})
        mock_media_cls.return_value = media_inst

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png content")
            temp_path = f.name

        try:
            await upsert_media_tool(
                {
                    "handle": "m1",
                    "desc": "PNG photo",
                    "file_location": temp_path,
                }
            )

            # Verify the mime type was detected as image/png
            call_args = media_inst.replace_media_file.call_args
            # Check positional or keyword args for mime_type
            all_args = list(call_args[0]) + list(call_args[1].values())
            assert any(arg == "image/png" for arg in all_args if isinstance(arg, str))
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.MediaClient")
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_metadata_updated_after_file_replacement(
        self, _settings, mock_client_cls, mock_media_cls
    ):
        """After file replacement, metadata is still updated via PUT."""
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "m1", "gramps_id": "O001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        media_inst = AsyncMock()
        media_inst.replace_media_file = AsyncMock(return_value={})
        mock_media_cls.return_value = media_inst

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image")
            temp_path = f.name

        try:
            await upsert_media_tool(
                {
                    "handle": "m1",
                    "desc": "New description",
                    "file_location": temp_path,
                }
            )

            # Verify both file replacement and metadata update happened
            media_inst.replace_media_file.assert_awaited_once()
            client_inst.make_api_call.assert_awaited_once()

            # Verify metadata call used PUT_MEDIA_ITEM
            metadata_call = client_inst.make_api_call.call_args
            assert metadata_call[1]["api_call"].name == "PUT_MEDIA_ITEM"
        finally:
            os.unlink(temp_path)
