# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Media file operations for Gramps Web API client.

Provides specialized methods for uploading and replacing media files.
"""

import httpx

from .client import GrampsAPIError
from .models.parameters.base_params import BaseGetMultipleParams
from .resource_table import ENTITY_RESOURCES


class MediaClient:
    """Handles media file upload, replacement, and download operations."""

    def __init__(self, api_client):
        """Initialize MediaClient with reference to main API client."""
        self.client = api_client

    async def _send_with_auth_retry(
        self, method, url, *, content=None, content_type=None
    ):
        """Send a media request, retrying once after a 401 with token refresh.

        Mirrors GrampsWebAPIClient._make_request: on a 401, the stale bearer
        token is refreshed and the request is re-issued exactly once. An
        error status or a timeout raises GrampsAPIError with the status and
        whether the request was sent (#131); callers shape the response.

        Raises:
            GrampsAPIError: The response had an error status or timed out.
        """
        try:
            response = await self._request(method, url, content, content_type)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_msg = self.client._format_http_error(e)
            raise GrampsAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.ConnectError as e:
            raise GrampsAPIError(f"Cannot connect to Gramps API: {e}") from e
        except httpx.TimeoutException as e:
            # Reason: same rule as GrampsWebAPIClient._make_request; connect
            # and pool timeouts fail before any byte is sent.
            sent = not isinstance(e, (httpx.ConnectTimeout, httpx.PoolTimeout))
            raise GrampsAPIError(f"Request timeout: {e}", request_sent=sent) from e
        return response

    async def _request(self, method, url, content, content_type):
        """Send one request, and resend it once after a 401.

        Args:
            method: HTTP verb.
            url: Full request URL.
            content: Raw request body, or None.
            content_type: Content-Type header value, or None.

        Returns:
            The last httpx.Response.
        """
        headers = await self.client._get_headers()
        if content_type:
            headers["Content-Type"] = content_type
        response = await self.client.auth_manager.client.request(
            method=method, url=url, content=content, headers=headers
        )
        if response.status_code == 401:
            stale = (
                headers.get("Authorization", "").removeprefix("Bearer ").strip() or None
            )
            await self.client.auth_manager.force_refresh(stale)
            headers = await self.client._get_headers()
            if content_type:
                headers["Content-Type"] = content_type
            response = await self.client.auth_manager.client.request(
                method=method, url=url, content=content, headers=headers
            )
        return response

    async def upload_media_file(
        self, file_content: bytes, mime_type: str, tree_id: str = "default"
    ):
        """Upload a media file to Gramps.

        Args:
            file_content: Raw file bytes to upload.
            mime_type: MIME type of the file (e.g. "image/jpeg").
            tree_id: Tree identifier.

        Returns:
            API response dict.

        Raises:
            GrampsAPIError: If the API call fails.
        """
        url = self.client._build_url(tree_id, "media/")
        response = await self._send_with_auth_retry(
            "POST", url, content=file_content, content_type=mime_type
        )
        return response.json()

    async def handles_with_checksum(
        self, checksum: str, tree_id: str = "default"
    ) -> set[str]:
        """List the handles of the media records whose file has one checksum.

        Args:
            checksum: MD5 hex digest Gramps Web stores for an uploaded file.
            tree_id: Tree identifier.

        Returns:
            The matching handles.

        Raises:
            GrampsAPIError: If the API call fails.
        """
        records = await self.client.call_resource(
            "GET",
            ENTITY_RESOURCES["media"].collection_path,
            BaseGetMultipleParams.model_validate(
                {"gql": f'checksum = "{checksum}"', "keys": "handle"}
            ),
            tree_id=tree_id,
        )
        return {record["handle"] for record in records}

    async def download_media_file(
        self, handle: str, tree_id: str = "default"
    ) -> tuple[bytes, str]:
        """Download a media file from Gramps.

        Args:
            handle: Media object handle.
            tree_id: Tree identifier.

        Returns:
            Tuple of (file_bytes, content_type).

        Raises:
            GrampsAPIError: If the API call fails.
        """
        url = self.client._build_url(tree_id, f"media/{handle}/file")

        response = await self._send_with_auth_retry("GET", url)
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type

    async def replace_media_file(
        self,
        file_content: bytes,
        handle: str,
        mime_type: str,
        tree_id: str = "default",
    ) -> dict:
        """Replace the file of an existing media record.

        Uses PUT /media/{handle}/file to upload a new file for an
        existing media object.

        Args:
            file_content: Raw file bytes to upload.
            handle: Handle of the existing media record.
            mime_type: MIME type of the file (e.g. "image/jpeg").
            tree_id: Tree identifier.

        Returns:
            API response dict.

        Raises:
            GrampsAPIError: If the API call fails.
        """
        url = self.client._build_url(tree_id, f"media/{handle}/file")

        response = await self._send_with_auth_retry(
            "PUT", url, content=file_content, content_type=mime_type
        )
        if not response.text.strip():
            return {}
        return response.json()
