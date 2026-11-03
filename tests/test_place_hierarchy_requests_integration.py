# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for the request cost of place hierarchy formatting (#122).

format_place once sent one GET per enclosing level. These tests count the
requests that reach the seed instance and pin the cost at one GET per place,
whatever the depth of its hierarchy.

The seed titles all but three places, and a title short-circuits the walk, so
the tests build their own untitled four-level chain.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.person_handler import format_person
from src.gramps_mcp.handlers.place_handler import format_place
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration

LEVELS = [("Country", "Country"), ("State", "State"), ("County", "County")]
CITY = f"{TEST_PREFIX}City"
HIERARCHY = ", ".join([CITY] + [f"{TEST_PREFIX}{name}" for name, _ in reversed(LEVELS)])


async def _upsert(entity: str, payload: dict) -> str:
    """Create an entity through its MCP upsert handler and return its handle."""
    text = (await UPSERT_HANDLERS[entity](payload))[0].text
    assert "Error:" not in text, f"Expected success: {text}"
    return extract_handle(text)


async def _create_city() -> str:
    """Create an untitled City in County, State, Country and return its handle."""
    enclosing = None
    for name, place_type in LEVELS:
        payload = {"name": {"value": f"{TEST_PREFIX}{name}"}, "place_type": place_type}
        if enclosing:
            payload["enclosed_by"] = enclosing
        enclosing = await _upsert("place", payload)
    return await _upsert(
        "place",
        {"name": {"value": CITY}, "place_type": "City", "enclosed_by": enclosing},
    )


def _record_requests(client: GrampsWebAPIClient, monkeypatch) -> list:
    """Record the URL of every request the client sends from now on.

    Args:
        client (GrampsWebAPIClient): Client whose HTTP requests to record.
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        list: URLs, appended as requests go out.
    """
    urls = []
    http = client.auth_manager.client
    send = http.request

    async def recording_request(method, url, **kwargs):
        urls.append(str(url))
        return await send(method, url, **kwargs)

    monkeypatch.setattr(http, "request", recording_request)
    return urls


@pytest.mark.asyncio
async def test_multi_level_place_costs_one_request(monkeypatch):
    """A place four levels deep renders its full hierarchy from one GET."""
    tree_id = get_settings().gramps_tree_id
    client = GrampsWebAPIClient()
    try:
        handle = await _create_city()
        urls = _record_requests(client, monkeypatch)

        rendered = await format_place(client, tree_id, handle, inline=True)

        assert (rendered, len(urls)) == (HIERARCHY, 1)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_person_search_sends_one_place_request_per_place(monkeypatch):
    """A person born four levels deep costs one place request in search output."""
    tree_id = get_settings().gramps_tree_id
    client = GrampsWebAPIClient()
    try:
        # Reason: a person created through upsert_person keeps birth_ref_index
        # -1, so format_person prints no birth line for it. Repoint a seed
        # person's birth event instead; the per-run reset restores it.
        person = (
            await client.make_api_call(
                ApiCalls.GET_PEOPLE,
                tree_id=tree_id,
                params=BaseGetMultipleParams(
                    gql="birth_ref_index >= 0",
                    sort="-gramps_id",
                    pagesize=1,
                    keys="handle,birth_ref_index,event_ref_list",
                ),
            )
        )[0]
        handle = person["handle"]
        birth = person["event_ref_list"][person["birth_ref_index"]]["ref"]
        await _upsert("event", {"handle": birth, "place": await _create_city()})
        urls = _record_requests(client, monkeypatch)

        rendered = await format_person(client, tree_id, handle)

        place_urls = [url for url in urls if "/places/" in url]
        assert (f"- {HIERARCHY}\n" in rendered, len(place_urls)) == (True, 1)
    finally:
        await client.close()
