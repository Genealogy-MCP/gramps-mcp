# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for upsert_place alt_names round-trip (issue #61).

PlaceSaveParams accepts alt_names as plain strings. The API needs each one as a
PlaceName object, so to_api_payload() wraps them. These tests confirm the
wrapping survives a real create and a real update.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import upsert_place_tool

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


def _alt_name_values(place_data: dict) -> list[str]:
    """Pull the plain string values out of a place's alt_names."""
    return [entry["value"] for entry in place_data.get("alt_names", [])]


class TestPlaceAltNamesRoundTrip:
    """String alt_names reach the API as PlaceName objects."""

    @pytest.mark.asyncio
    async def test_create_place_with_alt_names(self):
        """alt_names strings on create are stored as PlaceName objects."""
        result = await upsert_place_tool(
            {
                "name": {"value": f"{TEST_PREFIX}Piedimonte Matese"},
                "place_type": "City",
                "alt_names": [f"{TEST_PREFIX}Piedimonte d'Alife"],
            }
        )
        text = result[0].text
        assert "Error:" not in text, f"Expected success: {text}"
        place_handle = extract_handle(text)

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            place_data = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE,
                tree_id=settings.gramps_tree_id,
                handle=place_handle,
            )
            assert _alt_name_values(place_data) == [
                f"{TEST_PREFIX}Piedimonte d'Alife"
            ], f"Unexpected alt_names: {place_data.get('alt_names')}"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_update_place_alt_names_merges_by_default(self):
        """The default list_mode='merge' appends to stored alt_names (#82)."""
        create_result = await upsert_place_tool(
            {
                "name": {"value": f"{TEST_PREFIX}Napoli"},
                "place_type": "City",
                "alt_names": [f"{TEST_PREFIX}Neapolis"],
            }
        )
        place_handle = extract_handle(create_result[0].text)

        update_result = await upsert_place_tool(
            {
                "handle": place_handle,
                "alt_names": [f"{TEST_PREFIX}Parthenope"],
            }
        )
        assert "Error:" not in update_result[0].text, update_result[0].text

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            place_data = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE,
                tree_id=settings.gramps_tree_id,
                handle=place_handle,
            )
            assert _alt_name_values(place_data) == [
                f"{TEST_PREFIX}Neapolis",
                f"{TEST_PREFIX}Parthenope",
            ], f"Unexpected alt_names: {place_data.get('alt_names')}"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_update_place_alt_names_merge_is_idempotent(self):
        """Re-PUTting the same alt_name leaves a single stored entry (#82)."""
        create_result = await upsert_place_tool(
            {
                "name": {"value": f"{TEST_PREFIX}Napoli"},
                "place_type": "City",
                "alt_names": [f"{TEST_PREFIX}Neapolis"],
            }
        )
        place_handle = extract_handle(create_result[0].text)

        update_result = await upsert_place_tool(
            {
                "handle": place_handle,
                "alt_names": [f"{TEST_PREFIX}Neapolis"],
            }
        )
        assert "Error:" not in update_result[0].text, update_result[0].text

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            place_data = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE,
                tree_id=settings.gramps_tree_id,
                handle=place_handle,
            )
            assert _alt_name_values(place_data) == [f"{TEST_PREFIX}Neapolis"], (
                f"Unexpected alt_names: {place_data.get('alt_names')}"
            )
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_update_place_alt_names_replace_mode_overwrites(self):
        """list_mode='replace' overwrites the stored alt_names (#82)."""
        create_result = await upsert_place_tool(
            {
                "name": {"value": f"{TEST_PREFIX}Napoli"},
                "place_type": "City",
                "alt_names": [f"{TEST_PREFIX}Neapolis"],
            }
        )
        place_handle = extract_handle(create_result[0].text)

        update_result = await upsert_place_tool(
            {
                "handle": place_handle,
                "alt_names": [f"{TEST_PREFIX}Parthenope"],
                "list_mode": "replace",
            }
        )
        assert "Error:" not in update_result[0].text, update_result[0].text

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            place_data = await client.make_api_call(
                api_call=ApiCalls.GET_PLACE,
                tree_id=settings.gramps_tree_id,
                handle=place_handle,
            )
            assert _alt_name_values(place_data) == [f"{TEST_PREFIX}Parthenope"], (
                f"Unexpected alt_names: {place_data.get('alt_names')}"
            )
        finally:
            await client.close()
