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
    upsert_citation_tool,
    upsert_family_tool,
    upsert_media_tool,
    upsert_person_tool,
    upsert_source_tool,
)

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


class TestFamilyChildRoundTrip:
    """Create family with child_handles and verify via GET."""

    @pytest.mark.asyncio
    async def test_create_family_with_child_round_trip(self):
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

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_text = family_result[0].text
        assert "Error:" not in family_text, f"Expected success: {family_text}"
        family_handle = extract_handle(family_text)

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
    async def test_clear_children_via_replace_mode(self):
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

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_handle = extract_handle(family_result[0].text)

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
    async def test_re_put_same_child_is_idempotent(self):
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

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_handle = extract_handle(family_result[0].text)

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
    async def test_media_ref_distinct_rects_both_survive(self):
        """Merge-PUT same media ref with a different rect: both crops survive."""
        media_result = await upsert_media_tool(
            {
                "file_location": "tests/sample/33SQ-GP8N-NLK.jpg",
                "desc": f"{TEST_PREFIX}Composite merge media",
            }
        )
        media_handle = extract_handle(media_result[0].text)

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


async def _make_person(label: str) -> str:
    """Create a test person and return its handle.

    Args:
        label (str): Distinguishing part of the person's first name.

    Returns:
        str: The new person's handle.
    """
    result = await upsert_person_tool(
        {
            "primary_name": {
                "first_name": f"{TEST_PREFIX}{label}",
                "surname_list": [{"surname": f"{TEST_PREFIX}Testing", "primary": True}],
            },
            "gender": 2,
        }
    )
    return extract_handle(result[0].text)


async def _make_citation(label: str) -> str:
    """Create a test source plus a citation on it, returning the citation handle.

    Args:
        label (str): Distinguishing part of the source title.

    Returns:
        str: The new citation's handle.
    """
    source_result = await upsert_source_tool({"title": f"{TEST_PREFIX}{label}"})
    source_handle = extract_handle(source_result[0].text)
    citation_result = await upsert_citation_tool(
        {"source_handle": source_handle, "page": f"{label} p. 1"}
    )
    return extract_handle(citation_result[0].text)


async def _get_family(handle: str) -> dict:
    """Read a family straight from the API.

    Args:
        handle (str): The family's handle.

    Returns:
        dict: The stored family object.
    """
    client = GrampsWebAPIClient()
    try:
        settings = get_settings()
        return await client.make_api_call(
            api_call=ApiCalls.GET_FAMILY,
            tree_id=settings.gramps_tree_id,
            handle=handle,
        )
    finally:
        await client.close()


class TestFamilyEvidenceRoundTrip:
    """upsert_family writes child_ref evidence, family citations and type.

    Guards #60, #62, #63 and #64: every one of these fields used to be dropped
    by FamilySaveParams while the tool still reported success.
    """

    @pytest.mark.asyncio
    async def test_citation_attaches_to_existing_child_edge(self):
        """A citation added to a child already in the family lands on that edge."""
        person_handle = await _make_person("EdgeEvidence")
        citation_handle = await _make_citation("EdgeEvidenceSource")

        family_result = await upsert_family_tool({"child_handles": [person_handle]})
        family_handle = extract_handle(family_result[0].text)

        update = await upsert_family_tool(
            {
                "handle": family_handle,
                "child_ref_list": [
                    {"ref": person_handle, "citation_list": [citation_handle]}
                ],
            }
        )
        assert "Error:" not in update[0].text, f"Update failed: {update[0].text}"

        child_ref_list = (await _get_family(family_handle))["child_ref_list"]
        assert len(child_ref_list) == 1, (
            f"Expected the edge to be updated, not duplicated: {child_ref_list}"
        )
        assert child_ref_list[0]["citation_list"] == [citation_handle]
        assert child_ref_list[0]["frel"] == "Birth"

    @pytest.mark.asyncio
    async def test_family_level_citation_persists(self):
        """A family-level citation_list is written and merged additively."""
        first_citation = await _make_citation("FamilyEvidenceOne")
        second_citation = await _make_citation("FamilyEvidenceTwo")

        family_result = await upsert_family_tool({"citation_list": [first_citation]})
        family_handle = extract_handle(family_result[0].text)

        update = await upsert_family_tool(
            {"handle": family_handle, "citation_list": [second_citation]}
        )
        assert "Error:" not in update[0].text, f"Update failed: {update[0].text}"

        family_data = await _get_family(family_handle)
        assert family_data["citation_list"] == [first_citation, second_citation]

    @pytest.mark.asyncio
    async def test_family_type_persists(self):
        """family_type reaches the stored record as the relationship type."""
        family_result = await upsert_family_tool({})
        family_handle = extract_handle(family_result[0].text)

        update = await upsert_family_tool(
            {"handle": family_handle, "family_type": "Married"}
        )
        assert "Error:" not in update[0].text, f"Update failed: {update[0].text}"

        assert (await _get_family(family_handle))["type"] == "Married"

    @pytest.mark.asyncio
    async def test_adopted_edge_survives_a_citation_update(self):
        """Omitting frel/mrel on update leaves a non-Birth relationship intact."""
        person_handle = await _make_person("AdoptedEdge")
        citation_handle = await _make_citation("AdoptedEdgeSource")

        family_result = await upsert_family_tool(
            {"child_ref_list": [{"ref": person_handle, "frel": "Adopted"}]}
        )
        family_handle = extract_handle(family_result[0].text)

        await upsert_family_tool(
            {
                "handle": family_handle,
                "child_ref_list": [
                    {"ref": person_handle, "citation_list": [citation_handle]}
                ],
            }
        )

        child_ref_list = (await _get_family(family_handle))["child_ref_list"]
        assert len(child_ref_list) == 1
        assert child_ref_list[0]["frel"] == "Adopted"
        assert child_ref_list[0]["citation_list"] == [citation_handle]
