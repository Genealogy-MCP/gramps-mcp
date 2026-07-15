# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Media object management for Gramps MCP tools.

Handles media file upload, download, creation, and updating including metadata merging.
"""

import logging
from typing import Any, List

from mcp.types import TextContent

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..config import get_settings
from ..media_client import MediaClient
from ..models.api_calls import ApiCalls
from ..models.parameters.media_params import MediaDownloadParams, MediaSaveParams
from ._compat import extract_arguments
from ._data_helpers import _extract_entity_data, _format_save_response
from ._errors import McpToolError, raise_tool_error

logger = logging.getLogger(__name__)


async def upsert_media_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """
    Create or update media files including object associations.
    """
    import mimetypes
    import os

    try:
        arguments = extract_arguments(ctx, params)
        validated = MediaSaveParams(**arguments) if arguments else None
        file_location = validated.file_location if validated else None

        settings = get_settings()
        tree_id = settings.gramps_tree_id

        client = GrampsWebAPIClient()
        media_client = MediaClient(client)
        try:
            if validated and validated.handle:
                # File replacement: upload new file before metadata update
                if file_location:
                    if not os.path.isfile(file_location):
                        raise FileNotFoundError(f"File not found: {file_location}")
                    with open(file_location, "rb") as f:
                        file_content = f.read()
                    mime_type, _ = mimetypes.guess_type(file_location)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                    try:
                        await media_client.replace_media_file(
                            file_content=file_content,
                            handle=validated.handle,
                            mime_type=mime_type,
                            tree_id=tree_id,
                        )
                    except GrampsAPIError as e:
                        if "409" in str(e):
                            logger.warning(
                                "File already exists (409 Conflict) "
                                "for handle %s — skipping re-upload, "
                                "proceeding with metadata update.",
                                validated.handle,
                            )
                        else:
                            raise

                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_MEDIA_ITEM,
                    params=validated,
                    tree_id=tree_id,
                    handle=validated.handle,
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
                if validated:
                    final_media_data.update(
                        validated.model_dump(
                            exclude={"file_location"}, exclude_none=True
                        )
                    )

                result = await client.make_api_call(
                    api_call=ApiCalls.PUT_MEDIA_ITEM,
                    params=final_media_data,
                    tree_id=tree_id,
                    handle=media_handle,
                )
                operation = "created"
                entity_data = _extract_entity_data(result)

            nudge_citation = operation == "created" and not getattr(
                validated, "citation_list", None
            )
            formatted_response = await _format_save_response(
                client, entity_data, "media", operation, tree_id, nudge_citation
            )
            return [TextContent(type="text", text=formatted_response)]

        finally:
            await client.close()

    except Exception as e:
        raise_tool_error(e, "media save")


async def download_media_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """Download a media file from Gramps Web to local disk."""
    import os

    try:
        arguments = extract_arguments(ctx, params)
        validated = MediaDownloadParams(**arguments)
        destination = validated.destination

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
            handle = validated.handle

            # Resolve gramps_id to handle if needed
            if not handle:
                results = await client.make_api_call(
                    api_call=ApiCalls.GET_MEDIA,
                    params={"gramps_id": validated.gramps_id},
                    tree_id=tree_id,
                )
                if not results:
                    raise McpToolError(
                        f"No media found with gramps_id '{validated.gramps_id}'. "
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
