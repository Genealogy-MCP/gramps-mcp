# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 Federico Castagnini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Media file operations for Gramps Web API client.

Provides specialized methods for uploading and replacing media files.
"""

import httpx

from .client import GrampsAPIError


class MediaClient:
    """Handles media file upload and replacement operations."""

    def __init__(self, api_client):
        """Initialize MediaClient with reference to main API client."""
        self.client = api_client

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
        headers = await self.client._get_headers()
        headers["Content-Type"] = mime_type

        response = await self.client.auth_manager.client.request(
            method="POST", url=url, content=file_content, headers=headers
        )
        response.raise_for_status()
        return response.json()

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
        headers = await self.client._get_headers()
        headers["Content-Type"] = mime_type

        try:
            response = await self.client.auth_manager.client.request(
                method="PUT", url=url, content=file_content, headers=headers
            )
            response.raise_for_status()
            if not response.text.strip():
                return {}
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = self.client._format_http_error(e)
            raise GrampsAPIError(error_msg) from e
