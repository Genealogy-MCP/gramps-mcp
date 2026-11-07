# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Per-entity write hooks the generic upsert runs (#103, slice S4 of #99).

``write_overlays.WRITE_BINDINGS`` binds them per entity: the person and
citation reference checks, the person re-save predicate, the media file
upload, and the tag summary line. The checks and the upload take
``(client, tree_id, params)`` with ``params`` the already parsed hand
model; the predicate takes ``params`` alone. Reference reads go through
the resource table paths, not ``ApiCalls`` members.
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
from typing import Any

from mcp_codemode import McpToolError

from .auth import GrampsAuthError
from .client import GrampsAPIError
from .handlers.note_handler import ELISION, has_elided_read
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


async def check_note_text(client: Any, tree_id: str, params: Any) -> None:
    """
    Reject a note update built on a shortened read of the stored text (#139).

    Args:
        client (Any): Gramps Web API client.
        tree_id (str): Active tree identifier.
        params (Any): Parsed ``NoteSaveParams``.

    Raises:
        McpToolError: The write would delete the stored text after the cut.
    """
    if not params.handle or ELISION not in (params.text or ""):
        return

    note = await _get_record(client, tree_id, "note", params.handle)
    stored = ((note or {}).get("text") or {}).get("string") or ""
    if has_elided_read(params.text, stored):
        raise McpToolError(
            f"Note '{params.handle}' was not saved: its text has a '{ELISION}', "
            "is shorter than the stored note, and has lost the stored ending, "
            "so it looks like a shortened read and saving would delete the "
            "rest. Use get for the full text, apply the edit to that, and save "
            f"again. To shorten the note on purpose, remove the '{ELISION}'."
        )


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

    Reason: the server picks the handle of an uploaded record, so a create
    cannot be checked by handle the way ``upsert_table._create`` checks the
    other entities (#131). Gramps Web stores the file's MD5 as the record's
    checksum, so the handles with that checksum are listed before the
    upload, and an upload that answers 5xx or times out is checked against
    the handles that appeared since.

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
            status other than 409. On an unknown upload outcome the message
            says whether a record was written.
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
                if e.status_code != 409:
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
    checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
    before = await media_client.handles_with_checksum(checksum, tree_id)
    try:
        upload_result = await media_client.upload_media_file(
            content, mime_type, tree_id
        )
    except GrampsAPIError as error:
        return await _check_upload(media_client, error, checksum, before, tree_id)
    if not (
        upload_result and isinstance(upload_result, list) and "new" in upload_result[0]
    ):
        raise GrampsAPIError("Media upload did not return the expected new object.")
    return upload_result[0]["new"]["handle"]


async def _check_upload(
    media_client: MediaClient,
    error: GrampsAPIError,
    checksum: str,
    before: set[str],
    tree_id: str,
) -> str:
    """
    Find the record a failed upload may have made.

    Args:
        media_client (MediaClient): Media client the upload went through.
        error (GrampsAPIError): The upload failure.
        checksum (str): MD5 hex digest of the uploaded file.
        before (set[str]): Handles with that checksum before the upload.
        tree_id (str): Active tree identifier.

    Returns:
        str: Handle of the one record the upload made.

    Raises:
        GrampsAPIError: The upload failed with a 4xx or never left, or no
            single new record was found; the message then says whether a
            retry is safe and how to check.
    """
    status = error.status_code
    if not error.request_sent or (status is not None and status < 500):
        raise error
    check = (
        "Search media with GQL "
        f'`checksum = "{checksum}"` before retrying, so a retry makes no '
        "duplicate."
    )
    try:
        new = await media_client.handles_with_checksum(checksum, tree_id) - before
    except (GrampsAPIError, GrampsAuthError) as lookup:
        raise GrampsAPIError(
            f"{error} The media may have been written. {check}",
            status_code=status,
            request_sent=True,
        ) from lookup
    if len(new) == 1:
        handle = new.pop()
        logger.warning(
            "media upload failed (%s) but the record with handle %s is stored; "
            "saving its fields",
            error,
            handle,
        )
        return handle
    if not new and status is None:
        raise GrampsAPIError(
            f"{error} No new media has this file yet, but the server may "
            f"still be saving it. {check}",
            request_sent=True,
        ) from error
    if not new:
        raise GrampsAPIError(
            f"{error} Nothing was written: no new media has this file, so a "
            "retry makes no duplicate.",
            status_code=status,
        ) from error
    # Reason: another upload of the same file ran meanwhile; which new
    # record is this one cannot be told apart.
    raise GrampsAPIError(
        f"{error} The media may have been written. {check}",
        status_code=status,
        request_sent=True,
    ) from error


def has_event_refs(params: Any) -> bool:
    """
    Tell whether a person create needs a re-save to set its event indexes.

    Reason: Gramps Web runs ``set_birth_death_index`` in ``update_object``
    but not in ``add_object`` (gramps-webapi 3.25.1), so a POSTed person
    keeps ``birth_ref_index`` and ``death_ref_index`` at -1 (#134).

    Args:
        params (Any): Parsed ``PersonData``.

    Returns:
        bool: True when the person references any event.
    """
    return bool(params.event_ref_list)


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
