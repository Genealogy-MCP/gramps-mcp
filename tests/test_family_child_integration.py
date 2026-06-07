# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for family child_handles round-trip through Gramps Web API.

Verifies that FamilySaveParams.to_api_payload() child_handles translation
works end-to-end: create a family with children, GET it back, confirm
child_ref_list structure. Also tests clearing children via replace mode.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import (
    upsert_family_tool,
    upsert_media_tool,
    upsert_person_tool,
)

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


class TestFamilyChildRoundTrip:
    """Create family with child_handles and verify via GET."""

    @pytest.mark.asyncio
    async def test_create_family_with_child_round_trip(self, cleanup_registry):
        """child_handles on create produces correct child_ref_list on GET."""
        person_result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}ChildRoundTrip",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Testing", "primary": True}
                    ],
                },
                "gender": 2,
            }
        )
        person_handle = extract_handle(person_result[0].text)
        cleanup_registry.track("person", person_handle)

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_text = family_result[0].text
        assert "Error:" not in family_text, f"Expected success: {family_text}"
        family_handle = extract_handle(family_text)
        cleanup_registry.track("family", family_handle)

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            family_data = await client.make_api_call(
                api_call=ApiCalls.GET_FAMILY,
                tree_id=settings.gramps_tree_id,
                handle=family_handle,
            )
            child_ref_list = family_data.get("child_ref_list", [])
            assert len(child_ref_list) == 1, (
                f"Expected 1 child ref, got {len(child_ref_list)}: {child_ref_list}"
            )
            ref = child_ref_list[0]
            assert ref["ref"] == person_handle
            assert ref["frel"] == "Birth"
            assert ref["mrel"] == "Birth"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_clear_children_via_replace_mode(self, cleanup_registry):
        """Empty child_handles with replace mode clears child_ref_list."""
        person_result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}ChildClear",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Testing", "primary": True}
                    ],
                },
                "gender": 2,
            }
        )
        person_handle = extract_handle(person_result[0].text)
        cleanup_registry.track("person", person_handle)

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_handle = extract_handle(family_result[0].text)
        cleanup_registry.track("family", family_handle)

        update_result = await upsert_family_tool(
            {
                "handle": family_handle,
                "child_handles": [],
                "list_mode": "replace",
            }
        )
        update_text = update_result[0].text
        assert "Error:" not in update_text, f"Expected success: {update_text}"

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            family_data = await client.make_api_call(
                api_call=ApiCalls.GET_FAMILY,
                tree_id=settings.gramps_tree_id,
                handle=family_handle,
            )
            child_ref_list = family_data.get("child_ref_list", [])
            assert child_ref_list == [], (
                f"Expected empty child_ref_list after replace, got: {child_ref_list}"
            )
        finally:
            await client.close()


class TestMergeCompositeIdentityRoundTrip:
    """End-to-end guards for composite-identity merge dedup (Issue #32)."""

    @pytest.mark.asyncio
    async def test_re_put_same_child_is_idempotent(self, cleanup_registry):
        """Re-PUT the same child via child_handles leaves exactly one child ref.

        Guards the enriched-existing vs minimal-new asymmetry: the stored child
        ref is enriched (typed ChildRefType enums) while a re-PUT sends a fresh
        child_handles list. Normalization must collapse them to one entry.
        """
        person_result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}Idempotentchild",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Testing", "primary": True}
                    ],
                },
                "gender": 2,
            }
        )
        person_handle = extract_handle(person_result[0].text)
        cleanup_registry.track("person", person_handle)

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_handle = extract_handle(family_result[0].text)
        cleanup_registry.track("family", family_handle)

        # Re-PUT the same child; merge must not append a duplicate.
        re_put = await upsert_family_tool(
            {"handle": family_handle, "child_handles": [person_handle]}
        )
        assert "Error:" not in re_put[0].text, f"Re-PUT failed: {re_put[0].text}"

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            family_data = await client.make_api_call(
                api_call=ApiCalls.GET_FAMILY,
                tree_id=settings.gramps_tree_id,
                handle=family_handle,
            )
            child_ref_list = family_data.get("child_ref_list", [])
            assert len(child_ref_list) == 1, (
                f"Expected 1 child ref after re-PUT, got {len(child_ref_list)}:"
                f" {child_ref_list}"
            )
            assert child_ref_list[0]["ref"] == person_handle
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_media_ref_distinct_rects_both_survive(self, cleanup_registry):
        """Merge-PUT same media ref with a different rect: both crops survive."""
        media_result = await upsert_media_tool(
            {
                "file_location": "tests/sample/33SQ-GP8N-NLK.jpg",
                "desc": f"{TEST_PREFIX}Composite merge media",
            }
        )
        media_handle = extract_handle(media_result[0].text)
        cleanup_registry.track("media", media_handle)

        person_result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}Mediacrop",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Testing", "primary": True}
                    ],
                },
                "gender": 2,
                "media_list": [{"ref": media_handle, "rect": [0, 0, 50, 50]}],
            }
        )
        person_handle = extract_handle(person_result[0].text)
        cleanup_registry.track("person", person_handle)

        update = await upsert_person_tool(
            {
                "handle": person_handle,
                "media_list": [{"ref": media_handle, "rect": [50, 50, 100, 100]}],
            }
        )
        assert "Error:" not in update[0].text, f"Update failed: {update[0].text}"

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            person_data = await client.make_api_call(
                api_call=ApiCalls.GET_PERSON,
                tree_id=settings.gramps_tree_id,
                handle=person_handle,
            )
            media_list = person_data.get("media_list", [])
            rects = [m.get("rect") for m in media_list]
            assert len(media_list) == 2, (
                f"Expected both crops to survive, got {len(media_list)}: {media_list}"
            )
            assert [0, 0, 50, 50] in rects
            assert [50, 50, 100, 100] in rects
        finally:
            await client.close()
