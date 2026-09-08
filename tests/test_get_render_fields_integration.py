# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for get rendering citation confidence/tags and note format
(issues #56, #87).

Both fields are written through the upsert tools (confidence on
upsert_citation, format on upsert_note, added in #87) and read back through
get, so these tests also cover the write path end to end.
"""

import pytest

from src.gramps_mcp.tools import (
    upsert_citation_tool,
    upsert_note_tool,
    upsert_source_tool,
    upsert_tag_tool,
)
from src.gramps_mcp.tools.search_details import get_tool

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


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
                "confidence": 4,
            }
        )
        citation_handle = extract_handle(citation_result[0].text)

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
            {
                "text": f"{TEST_PREFIX}formatted note body",
                "type": "Research",
                "format": 1,
            }
        )
        note_handle = extract_handle(note_result[0].text)

        result = await get_tool({"type": "note", "handle": note_handle})
        text = result[0].text
        assert "format: preformatted" in text, f"format missing: {text}"


class TestUpsertWritesConfidenceAndFormat:
    """Confidence and format are writable on update, not only on create (#87)."""

    @pytest.mark.asyncio
    async def test_citation_confidence_updated(self):
        source_result = await upsert_source_tool(
            {"title": f"{TEST_PREFIX}Confidence Update Source"}
        )
        source_handle = extract_handle(source_result[0].text)

        citation_result = await upsert_citation_tool(
            {
                "source_handle": source_handle,
                "page": f"{TEST_PREFIX}Page 2",
                "confidence": 2,
            }
        )
        citation_handle = extract_handle(citation_result[0].text)

        await upsert_citation_tool({"handle": citation_handle, "confidence": 4})

        result = await get_tool({"type": "citation", "handle": citation_handle})
        text = result[0].text
        assert "confidence: very high" in text, f"confidence not updated: {text}"

    @pytest.mark.asyncio
    async def test_note_format_updated(self):
        note_result = await upsert_note_tool(
            {
                "text": f"{TEST_PREFIX}format update body",
                "type": "Research",
                "format": 0,
            }
        )
        note_handle = extract_handle(note_result[0].text)

        await upsert_note_tool({"handle": note_handle, "format": 1})

        result = await get_tool({"type": "note", "handle": note_handle})
        text = result[0].text
        assert "format: preformatted" in text, f"format not updated: {text}"
