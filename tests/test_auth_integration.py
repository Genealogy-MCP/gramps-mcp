"""
Integration tests for auth module using actual Gramps Web API.

Only tests that require a running API instance live here.
Config-loading and singleton tests live in test_auth_unit.py.

Token-endpoint etiquette: Gramps Web throttles POST /token/ to ~1/second.
The AuthManager singleton caches its token for the whole session, so a normal
suite makes ~1 real token call total. Tests here that *force* a real auth must
(a) space themselves from any prior auth with a >1s sleep and (b) leave a valid
token cached in the shared singleton afterward, so following tests reuse it
instead of re-authenticating and tripping the rate limit.
"""

import asyncio
from unittest.mock import patch

import pytest

from src.gramps_mcp.auth import AuthManager

pytestmark = pytest.mark.integration


class TestAuthIntegration:
    """Test auth manager with actual Gramps Web API."""

    @pytest.mark.asyncio
    async def test_authentication_attempt(self):
        """Test authentication succeeds against a running Gramps instance."""
        auth = AuthManager()

        # authenticate() unconditionally hits the rate-limited /token/ endpoint;
        # drain any prior auth's 1/second window first.
        await asyncio.sleep(1.1)
        token = await auth.authenticate()

        assert isinstance(token, str)
        assert len(token) > 0
        assert auth._access_token == token
        assert auth._token_expires_at is not None

    @pytest.mark.asyncio
    async def test_get_token_flow(self):
        """Test complete token retrieval flow against a running Gramps instance."""
        auth = AuthManager()

        token = await auth.get_token()

        assert isinstance(token, str)
        assert len(token) > 0

        headers = auth.get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "Content-Type" in headers

    @pytest.mark.asyncio
    async def test_concurrent_get_token_authenticates_once(self):
        """Concurrent get_token() calls trigger exactly one authentication.

        Twenty coroutines race for a token while none is cached. A lock must
        serialize the refresh so authenticate() runs once and every caller
        receives the same token (no interleaved token-state writes).

        Operates on the shared singleton and leaves a freshly cached token so
        neighboring tests reuse it (see module docstring on token etiquette).
        """
        auth = AuthManager()

        # Let any prior auth's 1/second rate-limit window age out before the
        # single forced auth below.
        await asyncio.sleep(1.1)

        # Force a refresh-needed state on the shared singleton.
        auth._access_token = None
        auth._token_expires_at = None

        real_authenticate = auth.authenticate
        call_count = 0

        async def counting_authenticate():
            nonlocal call_count
            call_count += 1
            # Widen the race window so concurrent callers overlap.
            await asyncio.sleep(0.05)
            return await real_authenticate()

        with patch.object(auth, "authenticate", side_effect=counting_authenticate):
            results = await asyncio.gather(*[auth.get_token() for _ in range(20)])

        assert call_count == 1
        assert all(isinstance(t, str) and t for t in results)
        assert len(set(results)) == 1

    @pytest.mark.asyncio
    async def test_concurrent_force_refresh_authenticates_once(self):
        """Concurrent force_refresh(stale) calls re-authenticate exactly once.

        Twenty coroutines pass the same stale token to force_refresh(). Only the
        first should re-authenticate; the rest observe the changed token and
        return it. All receive an identical, non-empty token that differs from
        the stale one.

        Operates on the shared singleton and leaves a freshly cached token so
        neighboring tests reuse it (see module docstring on token etiquette).
        """
        auth = AuthManager()

        # Let any prior auth's 1/second rate-limit window age out.
        await asyncio.sleep(1.1)

        stale = "MCP_TEST_stale_token"
        auth._access_token = stale
        auth._token_expires_at = None

        real_authenticate = auth.authenticate
        call_count = 0

        async def counting_authenticate():
            nonlocal call_count
            call_count += 1
            # Widen the race window so concurrent callers overlap.
            await asyncio.sleep(0.05)
            return await real_authenticate()

        with patch.object(auth, "authenticate", side_effect=counting_authenticate):
            results = await asyncio.gather(
                *[auth.force_refresh(stale) for _ in range(20)]
            )

        assert call_count == 1
        assert all(isinstance(t, str) and t for t in results)
        assert len(set(results)) == 1
        assert results[0] != stale
