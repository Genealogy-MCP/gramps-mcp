# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for person-level citation_list round-trip (#76).

Every assertion reads the person back from the Gramps Web API rather than
trusting the tool's success message: create with citations, update under the
default merge, update under list_mode="replace", and an invalid-handle update.
"""

from typing import List

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import (
    upsert_citation_tool,
    upsert_person_tool,
    upsert_source_tool,
)
from src.gramps_mcp.tools._errors import McpToolError

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _make_citations(count: int, label: str) -> List[str]:
    """Create a source and `count` citations against it.

    Args:
        count (int): How many citations to create.
        label (str): Distinguishing label for the test entities.

    Returns:
        List[str]: The handles of the created citations.
    """
    source_result = await upsert_source_tool({"title": f"{TEST_PREFIX}{label} Source"})
    source_handle = extract_handle(source_result[0].text)

    handles = []
    for index in range(count):
        citation_result = await upsert_citation_tool(
            {
                "source_handle": source_handle,
                "page": f"{TEST_PREFIX}{label} page {index}",
            }
        )
        handles.append(extract_handle(citation_result[0].text))
    return handles


async def _make_person(label: str, **extra) -> str:
    """Create a test person and return its handle.

    Args:
        label (str): Distinguishing label for the person's first name.
        **extra: Additional fields forwarded to upsert_person.

    Returns:
        str: The new person's handle.
    """
    payload = {
        "primary_name": {
            "first_name": f"{TEST_PREFIX}{label}",
            "surname_list": [{"surname": f"{TEST_PREFIX}Testing", "primary": True}],
        },
        "gender": 2,
    }
    payload.update(extra)
    result = await upsert_person_tool(payload)
    text = result[0].text
    assert "Error:" not in text, f"Expected success: {text}"
    return extract_handle(text)


async def _read_citation_list(handle: str) -> List[str]:
    """GET a person from the API and return its stored citation_list.

    Args:
        handle (str): The person's handle.

    Returns:
        List[str]: The citation handles stored on the person.
    """
    client = GrampsWebAPIClient()
    try:
        settings = get_settings()
        person = await client.make_api_call(
            api_call=ApiCalls.GET_PERSON,
            tree_id=settings.gramps_tree_id,
            handle=handle,
        )
        return person.get("citation_list", [])
    finally:
        await client.close()


class TestPersonCitationRoundTrip:
    """citation_list survives create and update through the API."""

    @pytest.mark.asyncio
    async def test_citations_on_create(self):
        """Citations passed on create are stored on the person record."""
        citations = await _make_citations(2, "PersonCiteCreate")
        person_handle = await _make_person("PersonCiteCreate", citation_list=citations)

        stored = await _read_citation_list(person_handle)
        assert sorted(stored) == sorted(citations)

    @pytest.mark.asyncio
    async def test_update_merges_and_dedups(self):
        """Default merge appends the new handle without duplicating the old."""
        citations = await _make_citations(2, "PersonCiteMerge")
        person_handle = await _make_person(
            "PersonCiteMerge", citation_list=[citations[0]]
        )

        await upsert_person_tool({"handle": person_handle, "citation_list": citations})

        stored = await _read_citation_list(person_handle)
        assert sorted(stored) == sorted(citations), (
            f"Expected merge-with-dedup, got {stored}"
        )

    @pytest.mark.asyncio
    async def test_update_replace_overwrites(self):
        """list_mode='replace' overwrites the stored citation_list."""
        citations = await _make_citations(2, "PersonCiteReplace")
        person_handle = await _make_person(
            "PersonCiteReplace", citation_list=[citations[0]]
        )

        await upsert_person_tool(
            {
                "handle": person_handle,
                "citation_list": [citations[1]],
                "list_mode": "replace",
            }
        )

        stored = await _read_citation_list(person_handle)
        assert stored == [citations[1]], f"Expected replace, got {stored}"

    @pytest.mark.asyncio
    async def test_update_with_invalid_person_handle_errors(self):
        """Updating a non-existent person handle reports an error."""
        citations = await _make_citations(1, "PersonCiteInvalid")

        with pytest.raises(McpToolError):
            await upsert_person_tool(
                {
                    "handle": "nonexistenthandle000000000",
                    "citation_list": citations,
                }
            )
