# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration test for birth_ref_index and death_ref_index on person create (#134).

Gramps Web sets both indexes when it updates a person but not when it adds
one, so a person created with a Birth and a Death event must still read back
with the indexes pointing at them and show "Born:" and "Died:" in search.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.search_basic import SEARCH_HANDLERS
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _create_event(event_type: str, year: int) -> str:
    """Create a dated event and return its handle.

    Args:
        event_type (str): Gramps event type name.
        year (int): Event year.

    Returns:
        str: Handle of the new event.
    """
    result = await UPSERT_HANDLERS["event"](
        {
            "type": event_type,
            "description": f"{TEST_PREFIX}{event_type} index",
            "date": {"dateval": [15, 6, year, False], "quality": 0, "modifier": 0},
        }
    )
    return extract_handle(result[0].text)


@pytest.mark.asyncio
async def test_created_person_points_at_birth_and_death():
    """Primary Birth and Death refs set both indexes and the search lines."""
    residence = await _create_event("Residence", 1890)
    birth = await _create_event("Birth", 1878)
    death = await _create_event("Death", 1950)
    first_name = f"{TEST_PREFIX}BirthDeathIndex"

    result = await UPSERT_HANDLERS["person"](
        {
            "primary_name": {
                "first_name": first_name,
                "surname_list": [{"surname": f"{TEST_PREFIX}Index"}],
            },
            "gender": 1,
            "event_ref_list": [
                {"ref": residence, "role": "Primary"},
                {"ref": birth, "role": "Primary"},
                {"ref": death, "role": "Primary"},
            ],
        }
    )
    handle = extract_handle(result[0].text)

    client = GrampsWebAPIClient()
    try:
        stored = await client.make_api_call(
            api_call=ApiCalls.GET_PERSON,
            tree_id=get_settings().gramps_tree_id,
            handle=handle,
        )
    finally:
        await client.close()
    found = await SEARCH_HANDLERS["person"](
        {"gql": f'primary_name.first_name = "{first_name}"'}
    )
    lines = found[0].text.splitlines()

    assert (
        stored["birth_ref_index"],
        stored["death_ref_index"],
        [ref["ref"] for ref in stored["event_ref_list"]],
        any(line.startswith("Born: 15 June 1878") for line in lines),
        any(line.startswith("Died: 15 June 1950") for line in lines),
    ) == (1, 2, [residence, birth, death], True, True), found[0].text
