# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Media file download for Gramps MCP tools.

Media create/update (with file upload) runs through the generic upsert
and ``write_hooks.upload_media`` (#103).
"""

import logging
from typing import Any, List

from mcp.types import TextContent

from ..client import get_client
from ..config import get_settings
from ..media_client import MediaClient
from ..models.api_calls import ApiCalls
from ..models.parameters.media_params import (
    MediaDownloadParams,
    MediaSearchParams,
)
from ._compat import extract_arguments
from ._errors import McpToolError, parse_params, raise_tool_error

logger = logging.getLogger(__name__)


async def download_media_tool(ctx: Any = None, params: Any = None) -> List[TextContent]:
    """Download a media file from Gramps Web to local disk."""
    import os

    try:
        arguments = extract_arguments(ctx, params)
        validated = parse_params(MediaDownloadParams, arguments)
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

        client = get_client()
        media_client = MediaClient(client)
        handle = validated.handle

        # Resolve gramps_id to handle if needed
        if not handle:
            results = await client.make_api_call(
                api_call=ApiCalls.GET_MEDIA,
                params=MediaSearchParams.model_validate(
                    {"gramps_id": validated.gramps_id}
                ),
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

    except Exception as e:
        raise_tool_error(e, "media download")
