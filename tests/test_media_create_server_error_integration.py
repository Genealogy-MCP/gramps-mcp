# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for a media create that answers 5xx (#131).

Gramps Web picks the handle of an uploaded media record, so the create is
checked by the file checksum it stores. The upload patches below send the
real upload and then report a 500, or report a 500 without sending it. The
client subclass fails the metadata PUT that follows a good upload. Each
test uploads its own file bytes, so no other record shares its checksum.
"""

import hashlib
import uuid

import pytest

from src.gramps_mcp.client import GrampsAPIError, GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.media_client import MediaClient
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import upsert_table
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration

_SERVER_ERROR = "Server error (500) at media/."
_REAL_UPLOAD = MediaClient.upload_media_file


async def _upload_then_500(self, *args, **kwargs):
    """
    Send the real upload, then report HTTP 500.

    Args:
        self (MediaClient): The patched media client.
        *args: Forwarded to the real upload.
        **kwargs: Forwarded to the real upload.

    Raises:
        GrampsAPIError: Always, after the upload landed.
    """
    await _REAL_UPLOAD(self, *args, **kwargs)
    raise GrampsAPIError(_SERVER_ERROR, status_code=500)


async def _500_before_upload(self, *args, **kwargs):
    """
    Report HTTP 500 without sending the upload.

    Args:
        self (MediaClient): The patched media client.
        *args: Ignored.
        **kwargs: Ignored.

    Raises:
        GrampsAPIError: Always, with nothing sent.
    """
    raise GrampsAPIError(_SERVER_ERROR, status_code=500)


class _PutFails(GrampsWebAPIClient):
    """Client whose PUTs report HTTP 500 without reaching the server."""

    async def _make_request(self, method, url, *args, **kwargs):
        """
        Fail a PUT unsent; send every other request.

        Args:
            method (str): HTTP verb.
            url (str): Request URL.
            *args: Forwarded to the real request.
            **kwargs: Forwarded to the real request.

        Returns:
            Any: The real response for every verb but PUT.
        """
        if method == "PUT":
            raise GrampsAPIError("Server error (500) at media/x.", status_code=500)
        return await super()._make_request(method, url, *args, **kwargs)


@pytest.fixture
def upload_file(tmp_path):
    """Write a JPEG-named file with bytes no other record has; return it."""
    path = tmp_path / "probe.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0" + uuid.uuid4().bytes)
    return path


async def _stored_with_file(path) -> set[str]:
    """
    List the handles of the media records holding one file.

    Args:
        path: The uploaded file.

    Returns:
        set[str]: The matching handles.
    """
    checksum = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
    client = GrampsWebAPIClient()
    try:
        return await MediaClient(client).handles_with_checksum(
            checksum, get_settings().gramps_tree_id
        )
    finally:
        await client.close()


def _media(desc: str, path) -> dict:
    """
    Build an upsert_media create payload.

    Args:
        desc (str): Media description.
        path: File to upload.

    Returns:
        dict: The payload.
    """
    return {"desc": desc, "file_location": str(path)}


@pytest.mark.asyncio
async def test_landed_upload_reports_success(monkeypatch, upload_file):
    """A 500 after the upload stored the record saves its fields once."""
    desc = f"{TEST_PREFIX}Landed131"
    monkeypatch.setattr(MediaClient, "upload_media_file", _upload_then_500)

    result = await UPSERT_HANDLERS["media"](_media(desc, upload_file))

    handle = extract_handle(result[0].text)
    client = GrampsWebAPIClient()
    try:
        stored = await client.make_api_call(
            api_call=ApiCalls.GET_MEDIA_ITEM,
            tree_id=get_settings().gramps_tree_id,
            handle=handle,
        )
    finally:
        await client.close()
    assert (
        result[0].text.startswith("Successfully created media"),
        await _stored_with_file(upload_file),
        stored["desc"],
    ) == (True, {handle}, desc)


@pytest.mark.asyncio
async def test_unwritten_upload_says_retry_is_safe(monkeypatch, upload_file):
    """A 500 before the upload says nothing was written, and nothing is."""
    monkeypatch.setattr(MediaClient, "upload_media_file", _500_before_upload)

    with pytest.raises(McpToolError) as info:
        await UPSERT_HANDLERS["media"](
            _media(f"{TEST_PREFIX}Unwritten131", upload_file)
        )

    assert (
        "Nothing was written" in str(info.value),
        await _stored_with_file(upload_file),
    ) == (True, set())


@pytest.mark.asyncio
async def test_failed_put_names_the_stored_record(monkeypatch, upload_file):
    """A failed metadata PUT names the uploaded record; retrying on it works."""
    monkeypatch.setattr(upsert_table, "get_client", _PutFails)

    with pytest.raises(McpToolError) as info:
        await UPSERT_HANDLERS["media"](_media(f"{TEST_PREFIX}Put131", upload_file))

    (handle,) = await _stored_with_file(upload_file)
    monkeypatch.undo()
    desc = f"{TEST_PREFIX}PutRetried131"
    retried = await UPSERT_HANDLERS["media"]({"handle": handle, "desc": desc})

    assert (
        f"Retry with handle `{handle}`" in str(info.value),
        retried[0].text.startswith("Successfully updated media"),
        await _stored_with_file(upload_file),
    ) == (True, True, {handle})
