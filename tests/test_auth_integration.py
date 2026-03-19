"""
Integration tests for auth module using actual Gramps Web API.

Only tests that require a running API instance live here.
Config-loading and singleton tests live in test_auth_unit.py.
"""

import pytest

from src.gramps_mcp.auth import AuthManager

pytestmark = pytest.mark.integration


class TestAuthIntegration:
    """Test auth manager with actual Gramps Web API."""

    @pytest.mark.asyncio
    async def test_authentication_attempt(self):
        """Test authentication succeeds against a running Gramps instance."""
        auth = AuthManager()

        try:
            token = await auth.authenticate()

            assert isinstance(token, str)
            assert len(token) > 0
            assert auth._access_token == token
            assert auth._token_expires_at is not None
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_get_token_flow(self):
        """Test complete token retrieval flow against a running Gramps instance."""
        auth = AuthManager()

        try:
            token = await auth.get_token()

            assert isinstance(token, str)
            assert len(token) > 0

            headers = auth.get_headers()
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Bearer ")
            assert "Content-Type" in headers
        finally:
            await auth.close()
