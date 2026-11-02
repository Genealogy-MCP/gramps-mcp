# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Per-entity write hooks the generic upsert runs (#103, slice S4 of #99).

``write_overlays.WRITE_BINDINGS`` binds them per entity: the person and
citation reference checks, the media file upload, and the tag summary
line. Every hook takes ``(client, tree_id, params)`` with ``params`` the
already parsed hand model; reference reads go through the resource table
paths, not ``ApiCalls`` members.
"""

import asyncio
import logging
import mimetypes
import os
from typing import Any

from mcp_codemode import McpToolError

from .client import GrampsAPIError
from .media_client import MediaClient
from .resource_table import ENTITY_RESOURCES

logger = logging.getLogger(__name__)


async def _get_record(client: Any, tree_id: str, entity: str, handle: str) -> Any:
    """
    Read one record through its table item path.

    Args:
        client (Any): Gramps Web API client.
        tree_id (str): Active tree identifier.
        entity (str): Entity key of the table row.
        handle (str): Record handle.

    Returns:
        Any: The record, or a falsy value when the server returns none.
    """
    return await client.call_resource(
        "GET", ENTITY_RESOURCES[entity].item_path, tree_id=tree_id, handle=handle
    )


async def check_person_refs(client: Any, tree_id: str, params: Any) -> None:
    """
    Reject a person_ref_list naming the person itself or a missing person.

    Args:
        client (Any): Gramps Web API client.
        tree_id (str): Active tree identifier.
        params (Any): Parsed ``PersonData``.

    Raises:
        McpToolError: A self-reference, or a ref that resolves to no person.
    """
    if not params.person_ref_list:
        return

    refs = [entry.ref for entry in params.person_ref_list]

    if params.handle and params.handle in refs:
        raise McpToolError(
            "A person cannot be associated with itself. Remove the "
            f"person_ref_list entry whose ref equals this person's handle "
            f"('{params.handle}')."
        )

    async def _check(ref: str) -> None:
        if not await _get_record(client, tree_id, "person", ref):
            raise McpToolError(
                f"Associated person with handle '{ref}' not found. Ensure the "
                "person exists before referencing it in person_ref_list."
            )

    try:
        await asyncio.gather(*[_check(ref) for ref in refs])
    except GrampsAPIError as e:
        raise McpToolError(
            f"Associated person not found while validating person_ref_list: {e}. "
            "Ensure every referenced person exists."
        )


async def check_citation_source(client: Any, tree_id: str, params: Any) -> None:
    """
    Reject a citation whose source_handle is its own handle or missing.

    Args:
        client (Any): Gramps Web API client.
        tree_id (str): Active tree identifier.
        params (Any): Parsed ``CitationData``.

    Raises:
        McpToolError: A self-reference, or a source_handle naming no source.
    """
    if not params.source_handle:
        return

    if params.handle == params.source_handle:
        raise McpToolError(
            "Citation cannot reference itself as source. "
            "Set a different source_handle or remove the citation's handle."
        )

    missing = (
        f"Source with handle '{params.source_handle}' not found. Ensure the "
        "source exists before referencing it in a citation."
    )
    try:
        source = await _get_record(client, tree_id, "source", params.source_handle)
    except GrampsAPIError:
        raise McpToolError(missing)
    if not source:
        raise McpToolError(missing)


def _read_upload(file_location: str) -> tuple[bytes, str]:
    """
    Read a local file for upload and guess its MIME type.

    Args:
        file_location (str): Absolute local path of the file.

    Returns:
        tuple[bytes, str]: File bytes and MIME type
            (``application/octet-stream`` when unknown).

    Raises:
        FileNotFoundError: No file at that path.
    """
    if not os.path.isfile(file_location):
        raise FileNotFoundError(f"File not found: {file_location}")
    with open(file_location, "rb") as f:
        content = f.read()
    mime_type, _ = mimetypes.guess_type(file_location)
    return content, mime_type or "application/octet-stream"


async def upload_media(client: Any, tree_id: str, params: Any) -> str | None:
    """
    Upload the media file before the metadata write.

    On create the upload makes the record and the generic upsert PUTs the
    metadata onto the returned handle. On update with a file_location the
    stored file is replaced first; a 409 (same file already stored) is
    logged and skipped so the metadata update still runs.

    Args:
        client (Any): Gramps Web API client.
        tree_id (str): Active tree identifier.
        params (Any): Parsed ``MediaSaveParams``.

    Returns:
        str | None: Handle of the record the upload created, or None on
            update.

    Raises:
        ValueError: Create without file_location.
        FileNotFoundError: file_location names no file.
        GrampsAPIError: The upload failed, or a replace failed with a
            status other than 409.
    """
    media_client = MediaClient(client)

    if params.handle:
        if params.file_location:
            content, mime_type = _read_upload(params.file_location)
            try:
                await media_client.replace_media_file(
                    file_content=content,
                    handle=params.handle,
                    mime_type=mime_type,
                    tree_id=tree_id,
                )
            except GrampsAPIError as e:
                if "409" not in str(e):
                    raise
                logger.warning(
                    "File already exists (409 Conflict) for handle %s, "
                    "skipping re-upload, proceeding with metadata update.",
                    params.handle,
                )
        return None

    if not params.file_location:
        raise ValueError("file_location is required to create new media.")
    content, mime_type = _read_upload(params.file_location)
    upload_result = await media_client.upload_media_file(content, mime_type, tree_id)
    if not (
        upload_result and isinstance(upload_result, list) and "new" in upload_result[0]
    ):
        raise GrampsAPIError("Media upload did not return the expected new object.")
    return upload_result[0]["new"]["handle"]


def format_tag_save(entity_data: dict, operation: str) -> str:
    """
    Build the tag save confirmation; tags have no detail formatter.

    Args:
        entity_data (dict): Saved tag returned by the API.
        operation (str): ``"created"`` or ``"updated"``.

    Returns:
        str: Markdown confirmation with name, handle, color and priority.
    """
    return (
        f"Successfully {operation} tag:\n\n"
        f"**{entity_data.get('name', 'Unknown')}** "
        f"[{entity_data.get('handle', 'N/A')}]\n"
        f"Color: {entity_data.get('color', 'None')} | "
        f"Priority: {entity_data.get('priority', 0)}"
    )
