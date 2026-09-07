# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for get rendering citation confidence/tags and note format
(issue #56).

The upsert tools do not accept confidence or format, so these tests set those
fields via a direct API PUT after creating the entity, then verify get renders
them. Tags go through upsert_citation's tag_list, which BaseDataModel supports.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import (
    upsert_citation_tool,
    upsert_note_tool,
    upsert_source_tool,
    upsert_tag_tool,
)
from src.gramps_mcp.tools.search_details import get_tool

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _put_field(endpoint: str, handle: str, field: str, value) -> None:
    """Set one raw field on an entity via GET -> PUT.

    Uses the client's raw request path because make_api_call validates PUT
    bodies through the upsert param models, which drop fields like
    confidence/format that the upsert tools do not accept.
    """
    client = GrampsWebAPIClient()
    try:
        tree_id = get_settings().gramps_tree_id
        get_call = getattr(ApiCalls, f"GET_{endpoint.rstrip('s').upper()}")
        data = await client.make_api_call(
            api_call=get_call, tree_id=tree_id, handle=handle
        )
        data[field] = value
        url = client._build_url(tree_id, f"{endpoint}/{handle}")
        await client._make_request("PUT", url, json_data=data)
    finally:
        await client.close()


class TestGetRendersCitationFields:
    """get on a citation renders confidence and tag names (#56)."""

    @pytest.mark.asyncio
    async def test_citation_confidence_and_tags_rendered(self):
        source_result = await upsert_source_tool(
            {"title": f"{TEST_PREFIX}Confidence Source"}
        )
        source_handle = extract_handle(source_result[0].text)

        tag_a = await upsert_tag_tool({"name": f"{TEST_PREFIX}TagA"})
        tag_b = await upsert_tag_tool({"name": f"{TEST_PREFIX}TagB"})
        tag_handles = [
            extract_handle(tag_a[0].text),
            extract_handle(tag_b[0].text),
        ]

        citation_result = await upsert_citation_tool(
            {
                "source_handle": source_handle,
                "page": f"{TEST_PREFIX}Page 1",
                "tag_list": tag_handles,
            }
        )
        citation_handle = extract_handle(citation_result[0].text)

        # upsert_citation has no confidence param; set it via raw PUT
        await _put_field("citations", citation_handle, "confidence", 4)

        result = await get_tool({"type": "citation", "handle": citation_handle})
        text = result[0].text
        assert "confidence: very high" in text, f"confidence missing: {text}"
        assert f"{TEST_PREFIX}TagA" in text, f"tag A missing: {text}"
        assert f"{TEST_PREFIX}TagB" in text, f"tag B missing: {text}"


class TestGetRendersNoteFormat:
    """get on a note renders its format (#56)."""

    @pytest.mark.asyncio
    async def test_note_preformatted_format_rendered(self):
        note_result = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}formatted note body", "type": "Research"}
        )
        note_handle = extract_handle(note_result[0].text)

        # upsert_note has no format param; set it via raw PUT (1 = preformatted)
        await _put_field("notes", note_handle, "format", 1)

        result = await get_tool({"type": "note", "handle": note_handle})
        text = result[0].text
        assert "format: preformatted" in text, f"format missing: {text}"
