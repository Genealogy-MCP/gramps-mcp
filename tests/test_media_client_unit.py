"""
Unit tests for MediaClient 401-retry behaviour.

Each media method (download/upload/replace) must, on an HTTP 401, refresh
the stale token via auth_manager.force_refresh and retry the request exactly
once. Pure unit tests with mocked auth_manager.client.request (no Docker).
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.media_client import MediaClient


def _api_client(request_side_effect) -> MagicMock:
    """Build a mock api_client whose request yields the given responses."""
    api_client = MagicMock()
    api_client._get_headers = AsyncMock(return_value={"Authorization": "Bearer stale"})
    api_client._build_url = MagicMock(return_value="http://test/api/media/m1/file")
    api_client._format_http_error = MagicMock(return_value="Authentication failed.")
    api_client.auth_manager = MagicMock()
    api_client.auth_manager.force_refresh = AsyncMock()
    api_client.auth_manager.client = MagicMock()
    api_client.auth_manager.client.request = AsyncMock(side_effect=request_side_effect)
    return api_client


def _resp_401() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 401
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401",
            request=httpx.Request("GET", "http://test/api/media/m1/file"),
            response=httpx.Response(401),
        )
    )
    return resp


class TestDownloadMediaFile401Retry:
    """download_media_file recovers from a single 401."""

    @pytest.mark.asyncio
    async def test_retries_once_after_401(self):
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.content = b"jpeg bytes"
        resp_200.headers.get.return_value = "image/jpeg"
        resp_200.raise_for_status = MagicMock()

        api_client = _api_client([_resp_401(), resp_200])
        mc = MediaClient(api_client)

        result = await mc.download_media_file("m1")

        assert result == (b"jpeg bytes", "image/jpeg")
        api_client.auth_manager.force_refresh.assert_awaited_once_with("stale")
        assert api_client.auth_manager.client.request.await_count == 2

    @pytest.mark.asyncio
    async def test_persistent_401_raises_without_loop(self):
        api_client = _api_client([_resp_401(), _resp_401()])
        mc = MediaClient(api_client)

        with pytest.raises(GrampsAPIError, match="Authentication failed"):
            await mc.download_media_file("m1")

        assert api_client.auth_manager.client.request.await_count == 2


def _resp_200_json() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"handle": "m1"}'
    resp.json.return_value = {"handle": "m1"}
    resp.raise_for_status = MagicMock()
    return resp


class TestUploadMediaFile401Retry:
    """upload_media_file recovers from a single 401."""

    @pytest.mark.asyncio
    async def test_retries_once_after_401(self):
        api_client = _api_client([_resp_401(), _resp_200_json()])
        mc = MediaClient(api_client)

        result = await mc.upload_media_file(b"data", "image/jpeg")

        assert result == {"handle": "m1"}
        api_client.auth_manager.force_refresh.assert_awaited_once_with("stale")
        assert api_client.auth_manager.client.request.await_count == 2

    @pytest.mark.asyncio
    async def test_persistent_401_raises_without_loop(self):
        api_client = _api_client([_resp_401(), _resp_401()])
        mc = MediaClient(api_client)

        with pytest.raises(httpx.HTTPStatusError):
            await mc.upload_media_file(b"data", "image/jpeg")

        assert api_client.auth_manager.client.request.await_count == 2


class TestReplaceMediaFile401Retry:
    """replace_media_file recovers from a single 401."""

    @pytest.mark.asyncio
    async def test_retries_once_after_401(self):
        api_client = _api_client([_resp_401(), _resp_200_json()])
        mc = MediaClient(api_client)

        result = await mc.replace_media_file(b"data", "m1", "image/jpeg")

        assert result == {"handle": "m1"}
        api_client.auth_manager.force_refresh.assert_awaited_once_with("stale")
        assert api_client.auth_manager.client.request.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_body_after_retry_returns_dict(self):
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.text = ""
        resp_200.raise_for_status = MagicMock()

        api_client = _api_client([_resp_401(), resp_200])
        mc = MediaClient(api_client)

        result = await mc.replace_media_file(b"data", "m1", "image/jpeg")

        assert result == {}
        api_client.auth_manager.force_refresh.assert_awaited_once_with("stale")

    @pytest.mark.asyncio
    async def test_persistent_401_raises_without_loop(self):
        api_client = _api_client([_resp_401(), _resp_401()])
        mc = MediaClient(api_client)

        with pytest.raises(GrampsAPIError, match="Authentication failed"):
            await mc.replace_media_file(b"data", "m1", "image/jpeg")

        assert api_client.auth_manager.client.request.await_count == 2
