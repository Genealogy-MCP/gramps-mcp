# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
JWT Authentication handling for Gramps Web API.
"""

import asyncio
import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt
from pydantic import BaseModel, ValidationError

from .config import get_settings

logger = logging.getLogger(__name__)

# Reason: a failed login caches nothing, so without a cooldown every tool call
# logs in again within a second and trips the token endpoint's 1/second
# per-IP limit, replacing the real cause (bad credentials) with HTTP 429.
AUTH_FAILURE_COOLDOWN_SECONDS = 2.0
LOGIN_MAX_ATTEMPTS = 3


class GrampsAuthError(Exception):
    """Login at ``POST /token/`` failed.

    Attributes:
        status_code (int | None): HTTP status of the token response, or None
            when no response arrived (connection or timeout failure).
        error_type (str | None): The server's ``error.type`` (for example
            ``invalid_credentials``), or None when it sent none.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_type: str | None = None,
    ) -> None:
        """
        Store the server message, HTTP status and error type.

        Args:
            message (str): The server's error message, or a transport detail.
            status_code (int | None): HTTP status of the token response.
            error_type (str | None): The server's ``error.type`` value.
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


class _TokenBody(BaseModel):
    """Body of a successful token response."""

    access_token: str


class _TokenErrorDetail(BaseModel):
    """The ``error`` object of a failed token response."""

    message: str = ""
    type: str | None = None


class _TokenErrorBody(BaseModel):
    """Body of a failed token response: ``{"error": {...}}``."""

    error: _TokenErrorDetail


def _parse_access_token(response: httpx.Response) -> str:
    """Extract the access token from a successful token response.

    Args:
        response (httpx.Response): A 2xx response from the token endpoint.

    Returns:
        str: The access token.

    Raises:
        GrampsAuthError: If the body is not JSON or has no access_token.
    """
    # Reason: ValueError covers both a non-JSON body and pydantic's
    # ValidationError, which subclasses it.
    try:
        return _TokenBody.model_validate(response.json()).access_token
    except ValueError as e:
        raise GrampsAuthError(
            "Token response carried no access_token",
            status_code=response.status_code,
        ) from e


def _auth_error_from_response(response: httpx.Response) -> GrampsAuthError:
    """Build a GrampsAuthError from a non-2xx token response.

    Args:
        response: The failed ``POST /token/`` response.

    Returns:
        GrampsAuthError: Carries the status, and the server's message and
            type when the body parses.
    """
    try:
        detail = _TokenErrorBody.model_validate_json(response.content).error
    except ValidationError:
        return GrampsAuthError(
            f"HTTP {response.status_code}", status_code=response.status_code
        )
    return GrampsAuthError(
        detail.message or f"HTTP {response.status_code}",
        status_code=response.status_code,
        error_type=detail.type,
    )


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
        self._last_failure: Optional[GrampsAuthError] = None
        self._last_failure_at = 0.0

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

        A failure is remembered for AUTH_FAILURE_COOLDOWN_SECONDS; calls inside
        that window re-raise it without contacting the server. A 429 from the
        token endpoint is retried up to LOGIN_MAX_ATTEMPTS times in total.

        Returns:
            Access token string

        Raises:
            GrampsAuthError: If the login fails.
        """
        if (
            self._last_failure is not None
            and time.monotonic() - self._last_failure_at < AUTH_FAILURE_COOLDOWN_SECONDS
        ):
            raise self._last_failure
        try:
            response = await self._post_token()
            token = _parse_access_token(response)
        except GrampsAuthError as e:
            self._last_failure = e
            self._last_failure_at = time.monotonic()
            raise
        self._last_failure = None
        self._access_token = token

        # Set expiration time
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            if exp:
                self._token_expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            else:
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=15
                )
        except Exception as e:
            logger.warning(f"Failed to parse JWT expiry, defaulting to 15 min: {e}")
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        logger.info("Successfully authenticated with Gramps Web API")
        return token

    async def _post_token(self) -> httpx.Response:
        """POST the credentials, retrying a 429 with jittered backoff.

        Returns:
            httpx.Response: A successful token response.

        Raises:
            GrampsAuthError: On any non-2xx response once retries are spent,
                or when the server cannot be reached.
        """
        response = await self._post_credentials()
        for attempt in range(1, LOGIN_MAX_ATTEMPTS):
            if response.status_code != 429:
                break
            # Reason: the server sends no Retry-After; its limit is 1/second,
            # so wait at least that long, doubling, plus jitter.
            delay = 2 ** (attempt - 1) + random.uniform(0, 0.5)
            logger.warning(
                f"Login rate limited (HTTP 429), retrying in {delay:.1f}s "
                f"(attempt {attempt}/{LOGIN_MAX_ATTEMPTS})"
            )
            await asyncio.sleep(delay)
            response = await self._post_credentials()
        if response.is_success:
            return response
        raise _auth_error_from_response(response)

    async def _post_credentials(self) -> httpx.Response:
        """Send one ``POST /token/`` with the configured credentials.

        Returns:
            httpx.Response: The token endpoint's response, whatever its status.

        Raises:
            GrampsAuthError: If no response arrives.
        """
        try:
            return await self.client.post(
                "/token/",
                json={
                    "username": self.settings.gramps_username,
                    "password": self.settings.gramps_password,
                },
            )
        except httpx.HTTPError as e:
            raise GrampsAuthError(f"Cannot connect to Gramps API: {e}") from e

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
