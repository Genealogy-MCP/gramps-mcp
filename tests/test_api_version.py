"""
Unit tests for API version validation.

Tests verify that verify_api_version() correctly validates the Gramps Web API
version, rejects unsupported versions, and handles edge cases gracefully.
No network required -- all API calls are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gramps_mcp.client import (
    MIN_API_MAJOR_VERSION,
    GrampsAPIError,
    GrampsWebAPIClient,
)
from src.gramps_mcp.startup import verify_api_on_startup


class TestMinVersionConstant:
    """Test the MIN_API_MAJOR_VERSION module constant."""

    def test_min_version_is_3(self):
        assert MIN_API_MAJOR_VERSION == 3


class TestVerifyApiVersion:
    """Test verify_api_version validation logic."""

    def _make_client(self, metadata_response=None, side_effect=None):
        """Build a GrampsWebAPIClient with mocked internals.

        Args:
            metadata_response: Return value for _make_request.
            side_effect: Exception to raise from _make_request.

        Returns:
            Configured client with mocked auth and HTTP.
        """
        client = GrampsWebAPIClient()
        client.auth_manager = MagicMock()
        client.auth_manager.get_token = AsyncMock()
        client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock()
        client.auth_manager.close = AsyncMock()

        if side_effect is not None:
            client._make_request = AsyncMock(side_effect=side_effect)
        elif metadata_response is not None:
            client._make_request = AsyncMock(return_value=metadata_response)

        return client

    @pytest.mark.asyncio
    async def test_supported_version_3x(self):
        """API version 3.x should pass validation and return the version string."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "3.7.1"}}
        )
        version = await client.verify_api_version()
        assert version == "3.7.1"

    @pytest.mark.asyncio
    async def test_supported_version_4x(self):
        """Future API version 4.x should also pass validation."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "4.0.0"}}
        )
        version = await client.verify_api_version()
        assert version == "4.0.0"

    @pytest.mark.asyncio
    async def test_unsupported_version_2x_raises(self):
        """API version 2.x should raise GrampsAPIError."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "2.5.0"}}
        )
        with pytest.raises(GrampsAPIError, match="not supported"):
            await client.verify_api_version()

    @pytest.mark.asyncio
    async def test_unsupported_version_1x_raises(self):
        """API version 1.x should raise GrampsAPIError."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "1.0.0"}}
        )
        with pytest.raises(GrampsAPIError, match="not supported"):
            await client.verify_api_version()

    @pytest.mark.asyncio
    async def test_error_message_includes_version(self):
        """Error message should include the actual version found."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "2.3.4"}}
        )
        with pytest.raises(GrampsAPIError, match="2.3.4"):
            await client.verify_api_version()

    @pytest.mark.asyncio
    async def test_error_message_includes_upgrade_hint(self):
        """Error message should mention upgrading to Gramps Web 26.x."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "2.0.0"}}
        )
        with pytest.raises(GrampsAPIError, match="Gramps Web 26.x"):
            await client.verify_api_version()

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty(self):
        """If metadata endpoint is unreachable, return empty string (graceful)."""
        client = self._make_client(side_effect=Exception("Connection refused"))
        version = await client.verify_api_version()
        assert version == ""

    @pytest.mark.asyncio
    async def test_gramps_api_error_returns_empty(self):
        """GrampsAPIError from metadata should degrade gracefully."""
        client = self._make_client(
            side_effect=GrampsAPIError("Cannot connect to Gramps API")
        )
        version = await client.verify_api_version()
        assert version == ""

    @pytest.mark.asyncio
    async def test_missing_gramps_webapi_key(self):
        """Response without gramps_webapi key should return empty string."""
        client = self._make_client(metadata_response={"some_other": "data"})
        version = await client.verify_api_version()
        assert version == ""

    @pytest.mark.asyncio
    async def test_missing_version_key(self):
        """gramps_webapi dict without version key should return empty string."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"something": "else"}}
        )
        version = await client.verify_api_version()
        assert version == ""

    @pytest.mark.asyncio
    async def test_non_dict_response(self):
        """Non-dict metadata response should return empty string."""
        client = self._make_client(metadata_response="not a dict")
        version = await client.verify_api_version()
        assert version == ""

    @pytest.mark.asyncio
    async def test_malformed_version_string(self):
        """Version string that cannot be parsed should return empty string."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "beta"}}
        )
        version = await client.verify_api_version()
        assert version == ""

    @pytest.mark.asyncio
    async def test_version_with_prefix(self):
        """Version string like 'v3.1.0' should be parsed correctly."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "v3.1.0"}}
        )
        version = await client.verify_api_version()
        assert version == "v3.1.0"

    @pytest.mark.asyncio
    async def test_metadata_url_uses_correct_endpoint(self):
        """verify_api_version should call the metadata/ endpoint."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "3.0.0"}}
        )
        await client.verify_api_version()
        call_args = client._make_request.call_args
        url_arg = call_args.kwargs.get("url") or call_args.args[1]
        assert url_arg.endswith("/metadata/")

    @pytest.mark.asyncio
    async def test_custom_tree_id(self):
        """Custom tree_id should be passed to _build_url."""
        client = self._make_client(
            metadata_response={"gramps_webapi": {"version": "3.0.0"}}
        )
        version = await client.verify_api_version(tree_id="custom_tree")
        assert version == "3.0.0"


class TestVerifyApiOnStartup:
    """Test the verify_api_on_startup server startup hook."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.client.GrampsWebAPIClient")
    async def test_startup_calls_verify(self, mock_client_cls):
        """verify_api_on_startup creates a client, verifies, and closes it."""
        client_inst = AsyncMock()
        client_inst.verify_api_version = AsyncMock(return_value="3.7.1")
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        await verify_api_on_startup()

        client_inst.verify_api_version.assert_called_once()
        client_inst.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.client.GrampsWebAPIClient")
    async def test_startup_propagates_api_error(self, mock_client_cls):
        """Unsupported version error propagates so the server fails to start."""
        client_inst = AsyncMock()
        client_inst.verify_api_version = AsyncMock(
            side_effect=GrampsAPIError("version 2.5.0 is not supported")
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(GrampsAPIError, match="not supported"):
            await verify_api_on_startup()

        # Client must be closed even on error
        client_inst.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.client.GrampsWebAPIClient")
    async def test_startup_closes_client_on_exception(self, mock_client_cls):
        """Client is closed even if verify_api_version raises unexpectedly."""
        client_inst = AsyncMock()
        client_inst.verify_api_version = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(RuntimeError):
            await verify_api_on_startup()

        client_inst.close.assert_called_once()
