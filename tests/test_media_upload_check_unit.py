# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the media create outcome check (#131).

The server picks an uploaded record's handle, so ``upload_media`` lists the
handles that share the file's checksum before the upload and compares after
a failure. A scripted media client plays the upload and the two lookups.
"""

import hashlib
from types import SimpleNamespace

import pytest

from src.gramps_mcp import write_hooks
from src.gramps_mcp.auth import GrampsAuthError
from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.write_hooks import upload_media

_CONTENT = b"\xff\xd8\xff\xe0probe"
_CHECKSUM = hashlib.md5(_CONTENT, usedforsecurity=False).hexdigest()
_UPLOAD_500 = GrampsAPIError("Server error (500) at media/.", status_code=500)
_UPLOAD_TIMEOUT = GrampsAPIError("Request timeout: read.", request_sent=True)
_CREATED = [{"new": {"handle": "new1"}}]


class _ScriptedMedia:
    """Media client double playing an upload and a list of lookups."""

    def __init__(self, upload, lookups):
        """
        Store the scripted outcomes.

        Args:
            upload (Exception | list): Raised or returned by the upload.
            lookups (list): Raised or returned by each checksum lookup.
        """
        self.upload = upload
        self.lookups = list(lookups)
        self.checksums = []

    async def handles_with_checksum(self, checksum, tree_id="default"):
        """
        Record the checksum and play the next lookup.

        Args:
            checksum (str): MD5 hex digest asked for.
            tree_id (str): Tree id.

        Returns:
            set[str]: The scripted handles.
        """
        self.checksums.append(checksum)
        outcome = self.lookups.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def upload_media_file(self, content, mime_type, tree_id="default"):
        """
        Play the scripted upload.

        Args:
            content (bytes): File bytes.
            mime_type (str): MIME type.
            tree_id (str): Tree id.

        Returns:
            list: The scripted upload response.
        """
        if isinstance(self.upload, Exception):
            raise self.upload
        return self.upload


@pytest.fixture
def create(monkeypatch, tmp_path):
    """Install a scripted media client; return a runner for one create."""
    upload_file = tmp_path / "photo.jpg"
    upload_file.write_bytes(_CONTENT)
    params = SimpleNamespace(handle=None, file_location=str(upload_file))

    async def run(upload, *lookups):
        media = _ScriptedMedia(upload, lookups)
        monkeypatch.setattr(write_hooks, "MediaClient", lambda client: media)
        return media, await upload_media(None, "tree", params)

    return run


class TestUploadCheck:
    """A media upload that answers 5xx or times out is checked by checksum."""

    async def test_clean_upload_looks_up_once_by_file_md5(self, create):
        """A good upload returns its handle after one lookup by the file MD5."""
        media, handle = await create(_CREATED, {"old"})
        assert (handle, media.checksums) == ("new1", [_CHECKSUM])

    async def test_landed_upload_returns_the_new_handle(self, create):
        """A 500 with one new record under the checksum returns that record."""
        media, handle = await create(_UPLOAD_500, {"old"}, {"old", "new1"})
        assert (handle, media.checksums) == ("new1", [_CHECKSUM, _CHECKSUM])

    async def test_unwritten_upload_says_retry_is_safe(self, create):
        """A 500 with no new record says nothing was written."""
        with pytest.raises(GrampsAPIError) as info:
            await create(_UPLOAD_500, {"old"}, {"old"})
        assert (str(info.value), info.value.status_code) == (
            "Server error (500) at media/. Nothing was written: no new media "
            "has this file, so a retry makes no duplicate.",
            500,
        )

    async def test_unstored_timeout_says_check_before_retry(self, create):
        """A timeout with no new record may still land; it names the check."""
        with pytest.raises(GrampsAPIError) as info:
            await create(_UPLOAD_TIMEOUT, set(), set())
        assert (str(info.value), info.value.request_sent) == (
            "Request timeout: read. No new media has this file yet, but the "
            "server may still be saving it. Search media with GQL "
            f'`checksum = "{_CHECKSUM}"` before retrying, so a retry makes no '
            "duplicate.",
            True,
        )

    async def test_landed_timeout_returns_the_new_handle(self, create):
        """A timeout with one new record returns that record."""
        _, handle = await create(_UPLOAD_TIMEOUT, set(), {"new1"})
        assert handle == "new1"

    @pytest.mark.parametrize(
        "after",
        [
            {"old", "new1", "new2"},
            GrampsAPIError("Server error (502).", status_code=502),
            GrampsAuthError("Login failed.", status_code=500),
        ],
        ids=["two-new", "lookup-5xx", "lookup-auth"],
    )
    async def test_unconfirmed_upload_names_the_check(self, create, after):
        """Two new records or a failed lookup leave the outcome unknown."""
        with pytest.raises(GrampsAPIError) as info:
            await create(_UPLOAD_500, {"old"}, after)
        assert str(info.value) == (
            "Server error (500) at media/. The media may have been written. "
            f'Search media with GQL `checksum = "{_CHECKSUM}"` before '
            "retrying, so a retry makes no duplicate."
        )

    @pytest.mark.parametrize(
        "error",
        [
            GrampsAPIError("Request failed with status 413.", status_code=413),
            GrampsAPIError("Cannot connect to Gramps API: refused"),
        ],
        ids=["4xx", "unsent"],
    )
    async def test_known_failure_raises_as_is(self, create, error):
        """A 4xx or an unsent upload raises unchanged with no second lookup."""
        # Reason: one scripted lookup; a second would raise IndexError.
        with pytest.raises(GrampsAPIError) as info:
            await create(error, set())
        assert info.value is error
