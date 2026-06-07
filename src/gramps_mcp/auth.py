# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
JWT Authentication handling for Gramps Web API.
"""

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt

from .config import get_settings

logger = logging.getLogger(__name__)


class AuthManager:
    """Singleton JWT authentication for Gramps Web API."""

    _instance: Optional["AuthManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AuthManager":
        """Ensure only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                # Double-check pattern to prevent race conditions
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the authentication manager (only once)."""
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        self.settings = get_settings()
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._client = None
        self._loop = None
        self._auth_lock = None
        self._auth_lock_loop = None

        self._initialized = True
        logger.info("Singleton AuthManager instance created")

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (for testing purposes)."""
        with cls._lock:
            if cls._instance and hasattr(cls._instance, "_client"):
                # Note: This is synchronous cleanup for testing
                # In production, use the async close() method
                pass
            cls._instance = None

    async def close(self):
        """Close the HTTP client and clear references."""
        if hasattr(self, "_client") and self._client is not None:
            if not self._client.is_closed:
                await self._client.aclose()
            self._client = None
            self._loop = None
            logger.info("AuthManager HTTP client closed and references cleared")

    @property
    def client(self) -> httpx.AsyncClient:
        """
        Get the httpx.AsyncClient instance, creating it if necessary.
        Ensures the client is open and valid for the current asyncio event loop.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # Recreate client if: no client, client closed, or different event loop
        if (
            not hasattr(self, "_client")
            or self._client is None
            or self._client.is_closed
            or getattr(self, "_loop", None) != current_loop
        ):
            # Log reason for recreation
            existing_loop = getattr(self, "_loop", None)
            if existing_loop and current_loop != existing_loop:
                logger.info(
                    "HTTP client recreated due to event loop change in AuthManager"
                )
            else:
                logger.info("HTTP client recreated in AuthManager")

            # Create new client with current event loop
            base_url = str(self.settings.gramps_api_url).rstrip("/")
            if not base_url.endswith("/api"):
                base_url += "/api"

            self._client = httpx.AsyncClient(
                base_url=base_url, timeout=httpx.Timeout(timeout=30.0, connect=10.0)
            )
            self._loop = current_loop
        return self._client

    async def authenticate(self) -> str:
        """
        Authenticate with Gramps Web API and get access token.

        Returns:
            Access token string
        """
        try:
            response = await self.client.post(
                "/token/",
                json={
                    "username": self.settings.gramps_username,
                    "password": self.settings.gramps_password,
                },
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = str(data["access_token"])

            # Set expiration time
            try:
                payload = jwt.decode(
                    self._access_token, options={"verify_signature": False}
                )
                exp = payload.get("exp")
                if exp:
                    self._token_expires_at = datetime.fromtimestamp(
                        exp, tz=timezone.utc
                    )
                else:
                    self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                        minutes=15
                    )
            except Exception as e:
                logger.warning(f"Failed to parse JWT expiry, defaulting to 15 min: {e}")
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=15
                )

            logger.info("Successfully authenticated with Gramps Web API")
            assert self._access_token is not None
            return self._access_token

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                raise ValueError("Invalid username or password")
            raise ValueError(f"Authentication failed: HTTP {e.response.status_code}")
        except httpx.ConnectError as e:
            raise ValueError(f"Cannot connect to Gramps API: {e}")
        except Exception as e:
            raise ValueError(f"Authentication error: {e}")

    def _get_lock(self) -> asyncio.Lock:
        """Get an asyncio.Lock bound to the current running event loop.

        An asyncio.Lock binds to the loop it is first awaited on. Since this
        singleton spans event loops (mirroring the client property), the lock is
        recreated whenever the running loop differs from the one it was bound to.

        Returns:
            An asyncio.Lock valid for the current event loop.
        """
        current_loop = asyncio.get_running_loop()
        if self._auth_lock is None or self._auth_lock_loop != current_loop:
            self._auth_lock = asyncio.Lock()
            self._auth_lock_loop = current_loop
        return self._auth_lock

    def _token_is_valid(self) -> bool:
        """Check whether the cached access token is present and not near expiry.

        Applies a 60-second pre-expiry skew so a token about to expire is treated
        as invalid and refreshed proactively.

        Returns:
            True if the token is set and valid beyond the skew window.
        """
        if not self._access_token or not self._token_expires_at:
            return False
        return datetime.now(timezone.utc) < self._token_expires_at - timedelta(
            seconds=60
        )

    async def get_token(self) -> str:
        """
        Get a valid access token, authenticating if needed.

        Returns:
            Valid access token
        """
        if self._token_is_valid():
            assert self._access_token is not None
            return self._access_token
        async with self._get_lock():
            if self._token_is_valid():
                assert self._access_token is not None
                return self._access_token
            return await self.authenticate()

    async def force_refresh(self, stale_token: Optional[str]) -> str:
        """Re-authenticate, deduplicating concurrent refreshes after a 401.

        Re-authenticates only if the current cached token still matches
        ``stale_token``. If another concurrent caller already refreshed the
        token, the newer token is returned without firing a redundant POST
        /token/.

        Args:
            stale_token: The token that produced the failing request.

        Returns:
            A freshly obtained or already-refreshed access token.
        """
        async with self._get_lock():
            if self._access_token and self._access_token != stale_token:
                return self._access_token
            return await self.authenticate()

    def get_headers(self) -> dict:
        """
        Get authentication headers for API requests.

        Returns:
            Dict with Authorization header
        """
        if not self._access_token:
            raise ValueError("Not authenticated")

        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
