"""
Characterization integration test for concurrent family-detail fetches (#34).

The MCP-22 refactor replaced two serial per-member loops in format_family_detail
with bounded concurrent fan-outs: (1) the per-relative birth/death date lookups
(father, mother, each child) and (2) the per-event timeline pre-fetch. Both use
asyncio.gather, whose completion order is non-deterministic, so a naive rewrite
could shuffle CHILDREN or TIMELINE lines. This test pins the observable contract
against the real seed API -- a family with many children must render identically
across independent calls regardless of fetch completion order.
"""

import pytest
from dotenv import load_dotenv

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.family_detail_handler import format_family_detail
from src.gramps_mcp.models.api_calls import ApiCalls

load_dotenv()

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_family_detail_render_is_order_stable_across_calls():
    """Rendering the same many-children family twice yields identical output.

    A concurrent gather that lost input ordering would surface here as a diff
    between two independent renders of the same family -- reordered CHILDREN or
    TIMELINE lines, or member dates re-associated to the wrong person.
    """
    settings = get_settings()
    client = GrampsWebAPIClient()
    tree_id = settings.gramps_tree_id
    try:
        candidates = await client.make_api_call(
            ApiCalls.GET_FAMILIES,
            tree_id=tree_id,
            params={
                "gql": "child_ref_list.length >= 4",
                "pagesize": 1,
                "keys": "handle",
            },
        )
        if not candidates:
            pytest.skip("Seed tree has no family with >= 4 children")
        handle = candidates[0]["handle"]

        first = await format_family_detail(client, tree_id, handle)
        second = await format_family_detail(client, tree_id, handle)

        assert first == second
    finally:
        await client.close()
