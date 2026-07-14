"""
Characterization integration test for the concurrent timeline fetch (issue #45).

The MCP-22 refactor replaced the serial per-event GET_EVENT loop in
format_person_detail with a bounded concurrent pre-fetch. The primary risk of
that change is losing chronological ordering: asyncio.gather completion order is
non-deterministic, so a naive rewrite could shuffle timeline lines. This test
pins the observable contract against the real seed API -- rendering a
rich-timeline person must be stable and order-preserving regardless of fetch
completion order.
"""

import pytest
from dotenv import load_dotenv

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.handlers.person_detail_handler import format_person_detail
from src.gramps_mcp.models.api_calls import ApiCalls

load_dotenv()

pytestmark = pytest.mark.integration


def _timeline_block(rendered: str) -> str:
    """Extract the TIMELINE section, stopping at the next section header."""
    lines = rendered.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("TIMELINE:"))
    block = ["TIMELINE:"]
    for line in lines[start + 1 :]:
        if line.startswith("Attached "):
            break
        block.append(line)
    return "\n".join(block)


@pytest.mark.asyncio
async def test_timeline_render_is_order_stable_across_calls():
    """Rendering the same rich-timeline person twice yields identical output.

    A concurrent gather that lost input ordering would surface here as a diff
    between two independent renders of the same person.
    """
    settings = get_settings()
    client = GrampsWebAPIClient()
    tree_id = settings.gramps_tree_id
    try:
        candidates = await client.make_api_call(
            ApiCalls.GET_PEOPLE,
            tree_id=tree_id,
            params={
                "gql": "event_ref_list.length >= 4",
                "pagesize": 1,
                "keys": "handle",
            },
        )
        if not candidates:
            pytest.skip("Seed tree has no person with >= 4 events")
        handle = candidates[0]["handle"]

        first = await format_person_detail(client, tree_id, handle)
        second = await format_person_detail(client, tree_id, handle)

        assert _timeline_block(first) == _timeline_block(second)
        assert first == second
    finally:
        await client.close()
