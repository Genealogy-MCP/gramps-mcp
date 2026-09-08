# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration test guarding the media create round-trip (#71).

Creating media uploads the file, receives the server's Media object, and PUTs
it back with the caller's fields merged in. That object carries fields the
server computes and the write model does not declare, so extra="forbid" made
the PUT reject them and the create path now sends only writable fields. The
risk that introduces is the opposite failure: a field dropped from the PUT
body could be cleared server-side, breaking the link to the uploaded file.
This test holds that line.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.data_management_media import upsert_media_tool

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_created_media_keeps_its_server_computed_file_link():
    """A created media object still resolves to its uploaded file."""
    result = await upsert_media_tool(
        {
            "desc": f"{TEST_PREFIX}Checksum survival probe",
            "file_location": "tests/sample/33SQ-GP8N-NLK.jpg",
        }
    )
    handle = extract_handle(result[0].text)
    assert handle

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
        bool(stored["checksum"]),
        bool(stored["path"]),
        stored["mime"],
        stored["desc"],
    ) == (True, True, "image/jpeg", f"{TEST_PREFIX}Checksum survival probe")
