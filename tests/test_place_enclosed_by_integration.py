# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for place enclosure round-trip through Gramps Web API.

Every assertion reads the place back from the API rather than trusting the
tool's success message: the bug in #67 was a tool that reported success while
storing an empty placeref_list.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import upsert_place_tool

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _create_place(name: str, place_type: str, **extra) -> str:
    """Create a place through the MCP tool and return its handle.

    Args:
        name (str): Place name value.
        place_type (str): Gramps place type, e.g. "City".
        **extra: Further upsert_place parameters, e.g. enclosed_by.

    Returns:
        str: The handle of the created place.
    """
    result = await upsert_place_tool(
        {"name": {"value": name}, "place_type": place_type, **extra}
    )
    text = result[0].text
    assert "Error:" not in text, f"Expected success: {text}"
    return extract_handle(text)


async def _read_placeref_list(handle: str) -> list:
    """Fetch a place from the API and return its stored placeref_list.

    Args:
        handle (str): Handle of the place to read.

    Returns:
        list: The placeref_list exactly as Gramps stored it.
    """
    client = GrampsWebAPIClient()
    try:
        settings = get_settings()
        place = await client.make_api_call(
            api_call=ApiCalls.GET_PLACE,
            tree_id=settings.gramps_tree_id,
            handle=handle,
        )
        return place.get("placeref_list", [])
    finally:
        await client.close()


class TestEnclosedByRoundTrip:
    """enclosed_by must be persisted, not silently dropped."""

    @pytest.mark.asyncio
    async def test_create_with_enclosed_by_persists_parent(self):
        """A place created with enclosed_by is stored inside that parent."""
        parent = await _create_place(f"{TEST_PREFIX}EnclosureState", "State")
        child = await _create_place(
            f"{TEST_PREFIX}EnclosureCity", "City", enclosed_by=parent
        )

        placeref_list = await _read_placeref_list(child)

        assert [ref["ref"] for ref in placeref_list] == [parent], (
            f"Expected the parent handle to be stored, got: {placeref_list}"
        )

    @pytest.mark.asyncio
    async def test_update_adds_enclosure_to_existing_place(self):
        """enclosed_by on update attaches a top-level place to a parent."""
        parent = await _create_place(f"{TEST_PREFIX}EnclosureCountry", "Country")
        orphan = await _create_place(f"{TEST_PREFIX}EnclosureOrphan", "State")

        assert await _read_placeref_list(orphan) == []

        result = await upsert_place_tool({"handle": orphan, "enclosed_by": parent})
        assert "Error:" not in result[0].text, result[0].text

        placeref_list = await _read_placeref_list(orphan)
        assert [ref["ref"] for ref in placeref_list] == [parent]

    @pytest.mark.asyncio
    async def test_reparenting_replaces_rather_than_stacks(self):
        """A second enclosed_by moves the place instead of adding a parent."""
        first_parent = await _create_place(f"{TEST_PREFIX}EnclosureFirst", "State")
        second_parent = await _create_place(f"{TEST_PREFIX}EnclosureSecond", "State")
        child = await _create_place(
            f"{TEST_PREFIX}EnclosureMoved", "City", enclosed_by=first_parent
        )

        await upsert_place_tool({"handle": child, "enclosed_by": second_parent})

        placeref_list = await _read_placeref_list(child)
        assert [ref["ref"] for ref in placeref_list] == [second_parent], (
            f"Expected exactly one current parent, got: {placeref_list}"
        )

    @pytest.mark.asyncio
    async def test_repeated_enclosed_by_is_idempotent(self):
        """Re-sending the same enclosure does not duplicate the reference."""
        parent = await _create_place(f"{TEST_PREFIX}EnclosureIdemParent", "State")
        child = await _create_place(
            f"{TEST_PREFIX}EnclosureIdemChild", "City", enclosed_by=parent
        )

        await upsert_place_tool({"handle": child, "enclosed_by": parent})

        placeref_list = await _read_placeref_list(child)
        assert [ref["ref"] for ref in placeref_list] == [parent]
