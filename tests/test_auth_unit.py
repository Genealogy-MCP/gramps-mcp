"""
Unit tests for auth.py — AuthManager singleton, token lifecycle,
and HTTP client management.

All tests mock httpx.AsyncClient to avoid network calls.
AuthManager.reset_instance() is called in each test to isolate state.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import httpx
import jwt
import pytest

from src.gramps_mcp.auth import AuthManager


@pytest.fixture(autouse=True)
def reset_auth_singleton():
    """Reset AuthManager singleton before and after each test."""
    AuthManager.reset_instance()
    yield
    AuthManager.reset_instance()


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------


class TestSingleton:
    """Test AuthManager singleton pattern."""

    def test_same_instance_returned(self):
        a = AuthManager()
        b = AuthManager()
        assert a is b

    def test_reset_clears_instance(self):
        a = AuthManager()
        AuthManager.reset_instance()
        b = AuthManager()
        assert a is not b


# ---------------------------------------------------------------------------
# client property
# ---------------------------------------------------------------------------


class TestClientProperty:
    """Test the httpx.AsyncClient lifecycle in AuthManager."""

    @pytest.mark.asyncio
    async def test_creates_client_on_first_access(self):
        mgr = AuthManager()
        client = mgr.client
        assert isinstance(client, httpx.AsyncClient)
        await mgr.close()

    @pytest.mark.asyncio
    async def test_returns_cached_client(self):
        mgr = AuthManager()
        c1 = mgr.client
        c2 = mgr.client
        assert c1 is c2
        await mgr.close()

    @pytest.mark.asyncio
    async def test_recreates_closed_client(self):
        mgr = AuthManager()
        c1 = mgr.client
        await c1.aclose()
        c2 = mgr.client
        assert c1 is not c2
        await mgr.close()


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------


class TestAuthenticate:
    """Test authenticate with mocked HTTP responses.

    Uses patch.object on the AuthManager class to replace the `client`
    property with a mock for each test, restoring it automatically.
    """

    @pytest.mark.asyncio
    async def test_happy_path_extracts_token(self):
        mgr = AuthManager()
        mock_client = AsyncMock()

        exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        token_str = jwt.encode({"exp": exp}, "secret", algorithm="HS256")

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"access_token": token_str}
        mock_client.post = AsyncMock(return_value=resp)

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            token = await mgr.authenticate()

        assert token == token_str
        assert mgr._access_token == token_str
        assert mgr._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_token_without_exp_defaults_15min(self):
        mgr = AuthManager()
        mock_client = AsyncMock()

        token_str = jwt.encode({"sub": "user"}, "secret", algorithm="HS256")

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"access_token": token_str}
        mock_client.post = AsyncMock(return_value=resp)

        before = datetime.now(timezone.utc)
        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            await mgr.authenticate()

        assert mgr._token_expires_at is not None
        delta = mgr._token_expires_at - before
        assert timedelta(minutes=14) < delta < timedelta(minutes=16)

    @pytest.mark.asyncio
    async def test_jwt_decode_failure_defaults_15min(self):
        mgr = AuthManager()
        mock_client = AsyncMock()

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"access_token": "not.a.valid.jwt"}
        mock_client.post = AsyncMock(return_value=resp)

        before = datetime.now(timezone.utc)
        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            await mgr.authenticate()

        delta = mgr._token_expires_at - before
        assert timedelta(minutes=14) < delta < timedelta(minutes=16)

    @pytest.mark.asyncio
    async def test_403_raises_invalid_credentials(self):
        mgr = AuthManager()
        mock_client = AsyncMock()

        error = httpx.HTTPStatusError(
            "403",
            request=httpx.Request("POST", "http://test/api/token/"),
            response=httpx.Response(403),
        )
        resp = MagicMock()
        resp.raise_for_status = MagicMock(side_effect=error)
        resp.status_code = 403
        mock_client.post = AsyncMock(return_value=resp)

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            with pytest.raises(ValueError, match="Invalid username or password"):
                await mgr.authenticate()

    @pytest.mark.asyncio
    async def test_500_raises_http_code(self):
        mgr = AuthManager()
        mock_client = AsyncMock()

        error = httpx.HTTPStatusError(
            "500",
            request=httpx.Request("POST", "http://test/api/token/"),
            response=httpx.Response(500),
        )
        resp = MagicMock()
        resp.raise_for_status = MagicMock(side_effect=error)
        resp.status_code = 500
        mock_client.post = AsyncMock(return_value=resp)

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            with pytest.raises(ValueError, match="HTTP 500"):
                await mgr.authenticate()

    @pytest.mark.asyncio
    async def test_connect_error_raises(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            with pytest.raises(ValueError, match="Cannot connect"):
                await mgr.authenticate()


# ---------------------------------------------------------------------------
# get_token
# ---------------------------------------------------------------------------


class TestGetToken:
    """Test get_token caching and refresh logic."""

    def _mock_auth_manager(self) -> AuthManager:
        mgr = AuthManager()
        mgr._client = AsyncMock()
        mgr._loop = None
        return mgr

    @pytest.mark.asyncio
    async def test_no_token_calls_authenticate(self):
        mgr = self._mock_auth_manager()
        mgr.authenticate = AsyncMock(return_value="fresh_token")
        mgr._access_token = None

        token = await mgr.get_token()
        assert token == "fresh_token"
        mgr.authenticate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_valid_token_returned_cached(self):
        mgr = self._mock_auth_manager()
        mgr._access_token = "cached_token"
        mgr._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mgr.authenticate = AsyncMock(return_value="should_not_be_called")

        token = await mgr.get_token()
        assert token == "cached_token"
        mgr.authenticate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_expired_token_triggers_reauth(self):
        mgr = self._mock_auth_manager()
        mgr._access_token = "old_token"
        mgr._token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        mgr.authenticate = AsyncMock(return_value="new_token")

        token = await mgr.get_token()
        assert token == "new_token"
        mgr.authenticate.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_headers
# ---------------------------------------------------------------------------


class TestGetHeaders:
    """Test get_headers."""

    def test_no_token_raises(self):
        mgr = AuthManager()
        mgr._access_token = None

        with pytest.raises(ValueError, match="Not authenticated"):
            mgr.get_headers()

    def test_with_token(self):
        mgr = AuthManager()
        mgr._access_token = "test_token"

        headers = mgr.get_headers()
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    """Test close cleans up resources."""

    @pytest.mark.asyncio
    async def test_closes_open_client(self):
        mgr = AuthManager()
        # Access client to create it
        _ = mgr.client
        assert mgr._client is not None
        await mgr.close()
        assert mgr._client is None

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        mgr = AuthManager()
        mgr._client = None
        await mgr.close()
        assert mgr._client is None
