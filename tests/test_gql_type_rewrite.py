# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Integration tests for the GQL typed-enum name rewrite (issue #84).

Runs the documented ``type.string = "<Name>"`` syntax through the search
operation against the seeded Docker tree and asserts real rows come back.
Also probes the raw server behavior: the untranslated query must still
return empty from Gramps Web -- the day that probe fails, upstream fixed
GQL typed-enum matching and the rewrite layer can be deleted.
"""

import re

import pytest
from mcp.types import TextContent

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.search_basic import search_tool

pytestmark = pytest.mark.integration


def _found_count(result: list[TextContent]) -> int:
    assert len(result) == 1
    text = result[0].text
    assert "error" not in text.lower(), f"Error in response: {text}"
    match = re.search(r"Found (\d+)", text)
    assert match, f"Expected a 'Found N' header but got: {text}"
    return int(match.group(1))


class TestTypeNameFilters:
    """The documented name syntax returns real rows for every entity."""

    @pytest.mark.asyncio
    async def test_event_type_birth(self):
        result = await search_tool(
            {"type": "event", "gql": 'type.string = "Birth"', "max_results": 3}
        )
        assert _found_count(result) > 0

    @pytest.mark.asyncio
    async def test_event_type_marriage_unquoted(self):
        result = await search_tool(
            {"type": "event", "gql": "type.string = Marriage", "max_results": 3}
        )
        assert _found_count(result) > 0

    @pytest.mark.asyncio
    async def test_place_type_city(self):
        result = await search_tool(
            {"type": "place", "gql": 'place_type.string = "City"', "max_results": 3}
        )
        assert _found_count(result) > 0

    @pytest.mark.asyncio
    async def test_family_type_married(self):
        result = await search_tool(
            {"type": "family", "gql": 'type.string = "Married"', "max_results": 3}
        )
        assert _found_count(result) > 0

    @pytest.mark.asyncio
    async def test_compound_query_with_type_filter(self):
        result = await search_tool(
            {
                "type": "event",
                "gql": 'type.string = "Birth" and date.dateval[2] > 1850',
                "max_results": 3,
            }
        )
        assert _found_count(result) > 0

    @pytest.mark.asyncio
    async def test_rewrite_matches_ground_truth_count(self):
        """The rewritten query returns the same total as raw type.value."""
        client = GrampsWebAPIClient()
        try:
            tree_id = get_settings().gramps_tree_id
            raw = await client.make_api_call(
                api_call=ApiCalls.GET_TYPES_DEFAULT_MAP,
                tree_id=tree_id,
                datatype="event_types",
            )
            birth_value = next(int(v) for v, name in raw.items() if name == "Birth")
            ground_truth = await client.make_api_call(
                api_call=ApiCalls.GET_EVENTS,
                params={"gql": f"type.value = {birth_value}"},
                tree_id=tree_id,
            )
            expected = (
                len(ground_truth)
                if isinstance(ground_truth, list)
                else ground_truth.get("total_count")
            )
        finally:
            await client.close()

        result = await search_tool(
            {"type": "event", "gql": 'type.string = "Birth"', "max_results": 1}
        )
        assert _found_count(result) == expected


class TestUpstreamRegressionProbe:
    """The raw untranslated query still returns empty from the server.

    When this fails, upstream Gramps Web learned to evaluate
    ``type.string`` and the rewrite layer (issue #84) can be deleted.
    """

    @pytest.mark.asyncio
    async def test_raw_type_string_still_broken_upstream(self):
        client = GrampsWebAPIClient()
        try:
            response = await client.make_api_call(
                api_call=ApiCalls.GET_EVENTS,
                params={"gql": 'type.string = "Birth"'},
                tree_id=get_settings().gramps_tree_id,
            )
        finally:
            await client.close()
        rows = response if isinstance(response, list) else response.get("data", [])
        assert rows == [], (
            "Upstream Gramps Web now evaluates type.string natively -- "
            "delete the _gql_type_rewrite layer (issue #84)."
        )
