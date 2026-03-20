# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
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
Media object management for Gramps MCP tools.

Handles media file upload, download, creation, and updating including metadata merging.
"""

import logging
from typing import Dict, List

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..media_client import MediaClient
from ..models.api_calls import ApiCalls
from ..models.parameters.media_params import MediaDownloadParams, MediaSaveParams
from ._data_helpers import _extract_entity_data, _format_save_response
from ._errors import McpToolError, raise_tool_error

logger = logging.getLogger(__name__)


async def upsert_media_tool(arguments: Dict) -> List[TextContent]:
    """
    Create or update media files including object associations.
    """
    import mimetypes
    import os

    try:
        params = MediaSaveParams(**arguments) if arguments else None
        file_location = params.file_location if params else None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        media_client = MediaClient(client)
        try:
            if params and params.handle:
                # File replacement: upload new file before metadata update
                if file_location:
                    if not os.path.isfile(file_location):
                        raise FileNotFoundError(f"File not found: {file_location}")
                    with open(file_location, "rb") as f:
                        file_content = f.read()
                    mime_type, _ = mimetypes.guess_type(file_location)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    await media_client.replace_media_file(
                        file_content=file_content,
                        handle=params.handle,
                        mime_type=mime_type,
                        tree_id=tree_id,
                    )

                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_MEDIA_ITEM,
                    params=params,
                    tree_id=tree_id,
                    handle=params.handle,
                )
                operation = "updated"
                entity_data = _extract_entity_data(result)
            else:
                if not file_location:
                    raise ValueError("file_location is required to create new media.")
                if not os.path.isfile(file_location):
                    raise FileNotFoundError(f"File not found: {file_location}")

                with open(file_location, "rb") as f:
                    file_content = f.read()
                mime_type, _ = mimetypes.guess_type(file_location)
                if not mime_type:
                    mime_type = "application/octet-stream"

                upload_result = await media_client.upload_media_file(
                    file_content, mime_type, tree_id
                )

                if not (
                    upload_result
                    and isinstance(upload_result, list)
                    and "new" in upload_result[0]
                ):
                    raise GrampsAPIError(
                        "Media upload did not return the expected new object."
                    )
                initial_media_object = upload_result[0]["new"]
                media_handle = initial_media_object["handle"]

                final_media_data = initial_media_object.copy()
                if params:
                    final_media_data.update(
                        params.model_dump(exclude={"file_location"}, exclude_none=True)
                    )

                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_MEDIA_ITEM,
                    params=final_media_data,
                    tree_id=tree_id,
                    handle=media_handle,
                )
                operation = "created"
                entity_data = _extract_entity_data(result)

            formatted_response = await _format_save_response(
                client, entity_data, "media", operation, tree_id
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "media save")


async def download_media_tool(arguments: Dict) -> List[TextContent]:
    """Download a media file from Gramps Web to local disk."""
    import os

    try:
        params = MediaDownloadParams(**arguments)
        destination = params.destination

        # Path security checks (MCP-18, MCP-19)
        if not os.path.isabs(destination):
            raise McpToolError(
                f"Destination must be an absolute path, got: '{destination}'"
            )
        # Check raw input for traversal before normalization resolves it
        if ".." in destination.split(os.sep):
            raise McpToolError(
                f"Path traversal not allowed in destination: '{destination}'"
            )
        normalized = os.path.normpath(destination)
        parent = os.path.dirname(normalized)
        if not os.path.isdir(parent):
            raise McpToolError(f"Parent directory does not exist: '{parent}'")
        if os.path.isdir(normalized):
            raise McpToolError(
                f"Destination is a directory, not a file: '{destination}'"
            )

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        media_client = MediaClient(client)
        try:
            handle = params.handle

            # Resolve gramps_id to handle if needed
            if not handle:
                results = await client.make_api_call(
                    api_call=ApiCalls.GET_MEDIA,
                    params={"gramps_id": params.gramps_id},
                    tree_id=tree_id,
                )
                if not results:
                    raise McpToolError(
                        f"No media found with gramps_id '{params.gramps_id}'. "
                        "Use search to find the correct ID first."
                    )
                handle = results[0]["handle"]

            # Fetch metadata for the response summary
            metadata = await client.make_api_call(
                api_call=ApiCalls.GET_MEDIA_ITEM,
                params=None,
                tree_id=tree_id,
                handle=handle,
            )

            # Download the binary file
            file_content, content_type = await media_client.download_media_file(
                handle, tree_id
            )

            # Write to disk
            with open(normalized, "wb") as f:
                f.write(file_content)

            desc = metadata.get("desc", "")
            gramps_id = metadata.get("gramps_id", "")
            size_bytes = len(file_content)
            summary = (
                f"Downloaded media to {normalized}\n"
                f"Handle: {handle}\n"
                f"Gramps ID: {gramps_id}\n"
                f"Description: {desc}\n"
                f"MIME type: {content_type}\n"
                f"Size: {size_bytes} bytes"
            )
            return [TextContent(type="text", text=summary)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "media download")
