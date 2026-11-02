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

from src.gramps_mcp.auth import (
    AUTH_FAILURE_COOLDOWN_SECONDS,
    LOGIN_MAX_ATTEMPTS,
    AuthManager,
    GrampsAuthError,
)


def _token_error(status: int, message: str, error_type: str) -> httpx.Response:
    """Build a token-endpoint error response in gramps-webapi's body shape."""
    return httpx.Response(
        status,
        json={"error": {"code": status, "message": message, "type": error_type}},
    )


def _token_ok() -> httpx.Response:
    """Build a successful token response carrying a one-hour JWT."""
    exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    token = jwt.encode({"exp": exp}, "secret", algorithm="HS256")
    return httpx.Response(200, json={"access_token": token})


@pytest.fixture(autouse=True)
def _isolate_auth_singleton():
    """Save and restore the AuthManager singleton around each test.

    Auth unit tests call reset_instance() and create fresh instances.
    Without this guard, they destroy the shared token that integration
    tests rely on when both run in the same session.
    """
    saved = AuthManager._instance
    AuthManager._instance = None
    yield
    AuthManager._instance = saved


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
    """Test the httpx.AsyncClient lifecycle in AuthManager.

    Patches httpx.AsyncClient to avoid environment-dependent proxy config
    (e.g. SOCKS proxy) that would cause ImportError in CI or local envs.
    """

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.auth.httpx.AsyncClient")
    async def test_creates_client_on_first_access(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.is_closed = False
        mock_instance.aclose = AsyncMock()
        mock_cls.return_value = mock_instance

        mgr = AuthManager()
        client = mgr.client
        assert client is mock_instance
        await mgr.close()

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.auth.httpx.AsyncClient")
    async def test_returns_cached_client(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.is_closed = False
        mock_instance.aclose = AsyncMock()
        mock_cls.return_value = mock_instance

        mgr = AuthManager()
        c1 = mgr.client
        c2 = mgr.client
        assert c1 is c2
        await mgr.close()

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.auth.httpx.AsyncClient")
    async def test_recreates_closed_client(self, mock_cls):
        first_client = MagicMock()
        first_client.is_closed = False
        first_client.aclose = AsyncMock()

        second_client = MagicMock()
        second_client.is_closed = False
        second_client.aclose = AsyncMock()

        mock_cls.side_effect = [first_client, second_client]

        mgr = AuthManager()
        c1 = mgr.client
        await c1.aclose()
        first_client.is_closed = True

        c2 = mgr.client
        assert c1 is not c2
        assert c2 is second_client
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
    async def test_403_raises_typed_error_with_server_type(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value=_token_error(
                403, "Invalid username or password", "invalid_credentials"
            )
        )

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            with pytest.raises(GrampsAuthError) as exc_info:
                await mgr.authenticate()

        err = exc_info.value
        assert (str(err), err.status_code, err.error_type) == (
            "Invalid username or password",
            403,
            "invalid_credentials",
        )

    @pytest.mark.asyncio
    async def test_500_without_json_body_keeps_status(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=httpx.Response(500, text="boom"))

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            with pytest.raises(GrampsAuthError) as exc_info:
                await mgr.authenticate()

        err = exc_info.value
        assert (str(err), err.status_code, err.error_type) == ("HTTP 500", 500, None)

    @pytest.mark.asyncio
    async def test_success_without_access_token_raises_typed_error(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=httpx.Response(200, text="<html>"))

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            with pytest.raises(GrampsAuthError) as exc_info:
                await mgr.authenticate()

        err = exc_info.value
        assert (str(err), err.status_code, err.error_type) == (
            "Token response carried no access_token",
            200,
            None,
        )
        # Reason: a gateway answering 200 with HTML must not re-login on every
        # call either, or the 429 storm from #117 comes back.
        assert mgr._last_failure is err

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
            with pytest.raises(GrampsAuthError, match="Cannot connect") as exc_info:
                await mgr.authenticate()

        assert exc_info.value.status_code is None


# ---------------------------------------------------------------------------
# authenticate: failure cooldown and 429 backoff (issue #117)
# ---------------------------------------------------------------------------


class TestAuthenticateFailureHandling:
    """A failed login is cached for a cooldown; a 429 login is retried."""

    @pytest.mark.asyncio
    async def test_failure_is_reraised_within_cooldown_without_posting(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value=_token_error(
                403, "Invalid username or password", "invalid_credentials"
            )
        )

        with patch.object(
            AuthManager, "client", new_callable=PropertyMock, return_value=mock_client
        ):
            for _ in range(3):
                with pytest.raises(GrampsAuthError) as exc_info:
                    await mgr.authenticate()
                assert exc_info.value.error_type == "invalid_credentials"

        assert mock_client.post.await_count == 1

    def test_cooldown_is_at_least_one_second(self):
        assert AUTH_FAILURE_COOLDOWN_SECONDS >= 1.0

    @pytest.mark.asyncio
    async def test_login_retried_after_cooldown_expires(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=[
                _token_error(
                    403, "Invalid username or password", "invalid_credentials"
                ),
                _token_ok(),
            ]
        )
        clock = [100.0]

        with (
            patch.object(
                AuthManager,
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
            patch("src.gramps_mcp.auth.time.monotonic", side_effect=lambda: clock[0]),
        ):
            with pytest.raises(GrampsAuthError):
                await mgr.authenticate()
            clock[0] += AUTH_FAILURE_COOLDOWN_SECONDS + 0.1
            token = await mgr.authenticate()

        assert token == mgr._access_token
        assert mock_client.post.await_count == 2

    @pytest.mark.asyncio
    async def test_429_retried_with_backoff_then_succeeds(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=[httpx.Response(429), httpx.Response(429), _token_ok()]
        )

        with (
            patch.object(
                AuthManager,
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
            patch("src.gramps_mcp.auth.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            token = await mgr.authenticate()

        assert token == mgr._access_token
        assert mock_client.post.await_count == 3
        delays = [c.args[0] for c in sleep.await_args_list]
        assert len(delays) == 2
        assert all(d >= 1.0 for d in delays)

    @pytest.mark.asyncio
    async def test_429_gives_up_after_three_attempts(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=httpx.Response(429))

        with (
            patch.object(
                AuthManager,
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
            patch("src.gramps_mcp.auth.asyncio.sleep", new=AsyncMock()),
        ):
            with pytest.raises(GrampsAuthError) as exc_info:
                await mgr.authenticate()

        assert exc_info.value.status_code == 429
        assert mock_client.post.await_count == LOGIN_MAX_ATTEMPTS == 3

    @pytest.mark.asyncio
    async def test_403_is_not_retried(self):
        mgr = AuthManager()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value=_token_error(403, "Account disabled", "account_disabled")
        )

        with (
            patch.object(
                AuthManager,
                "client",
                new_callable=PropertyMock,
                return_value=mock_client,
            ),
            patch("src.gramps_mcp.auth.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            with pytest.raises(GrampsAuthError):
                await mgr.authenticate()

        assert (mock_client.post.await_count, sleep.await_count) == (1, 0)


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
    @patch("src.gramps_mcp.auth.httpx.AsyncClient")
    async def test_closes_open_client(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.is_closed = False
        mock_instance.aclose = AsyncMock()
        mock_cls.return_value = mock_instance

        mgr = AuthManager()
        _ = mgr.client
        assert mgr._client is not None
        await mgr.close()
        assert mgr._client is None
        mock_instance.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        mgr = AuthManager()
        mgr._client = None
        await mgr.close()
        assert mgr._client is None


# ---------------------------------------------------------------------------
# Config + initialization (no API calls, only env vars from conftest)
# ---------------------------------------------------------------------------


class TestConfigLoading:
    """Test configuration loading from env vars set by conftest.py."""

    def test_get_settings_loads_from_env(self):
        """Settings load from env vars set by pytest_configure."""
        from src.gramps_mcp.config import get_settings

        settings = get_settings()

        assert settings.gramps_api_url is not None
        assert settings.gramps_username is not None
        assert settings.gramps_password is not None
        assert settings.gramps_tree_id is not None

    def test_auth_manager_initialization(self):
        """Auth manager initializes with settings from env vars."""
        auth = AuthManager()

        assert auth.settings.gramps_api_url is not None
        assert auth.settings.gramps_username is not None
        assert auth.settings.gramps_password is not None
