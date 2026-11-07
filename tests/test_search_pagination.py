# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for how the list routes apply page and pagesize (#141).

Gramps Web cuts a list response only when page is sent, so these tests call
the client directly where the tools' own slicing would hide the server.
"""

import pytest

from src.gramps_mcp.client import get_client
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.parameters.tag_params import TagSearchParams
from src.gramps_mcp.overlays import collection_call, read_route
from src.gramps_mcp.tools import _gql_type_rewrite
from src.gramps_mcp.tools._resolve import resolve_gramps_id
from src.gramps_mcp.tools.search_basic import list_tags_tool, search_tool
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

pytestmark = pytest.mark.integration

_PARAMS, _API_CALL = read_route("person")


async def _list_people(params):
    """Call GET people/ directly and return the rows and response headers."""
    return await get_client().make_api_call(
        api_call=_API_CALL,
        params=params,
        tree_id=get_settings().gramps_tree_id,
        with_headers=True,
    )


class TestListRoutePaging:
    """Record what the pinned Gramps Web image does with page and pagesize."""

    @pytest.mark.asyncio
    async def test_pagesize_without_page_returns_every_row(self):
        rows, _ = await _list_people(_PARAMS(pagesize=2))
        assert len(rows) > 2

    @pytest.mark.asyncio
    async def test_page_and_pagesize_cut_the_response(self):
        rows, headers = await _list_people(_PARAMS(page=1, pagesize=2))
        assert len(rows) == 2
        assert int(headers["x-total-count"]) > 2

    @pytest.mark.asyncio
    async def test_gramps_id_filter_returns_one_row_without_page(self):
        """resolve_gramps_id sends no page and is safe: the filter ends the list."""
        first, _ = await _list_people(_PARAMS(page=1, pagesize=1))
        gramps_id, handle = first[0]["gramps_id"], first[0]["handle"]

        rows, _ = await _list_people(_PARAMS(gramps_id=gramps_id, pagesize=1))

        assert [row["handle"] for row in rows] == [handle]
        assert await resolve_gramps_id("person", gramps_id) == handle


class TestSearchPaging:
    """search reports the server's total for a page it cut."""

    @pytest.mark.asyncio
    async def test_header_reports_server_total(self):
        result = await search_tool(
            {"type": "person", "gql": "gender = 1", "max_results": 2}
        )
        header = result[0].text.splitlines()[0]
        total = int(header.split()[1])
        assert total > 2
        assert "(showing 2)" in header

    @pytest.mark.asyncio
    async def test_custom_name_found_past_the_first_custom_rows(self):
        """A rare custom name still matches behind 434 seeded LVG rows."""
        name = "MCP_TEST_RareType"
        for _ in range(2):
            await UPSERT_HANDLERS["event"]({"type": name})
        _gql_type_rewrite._CUSTOM_NAMES_CACHE.clear()

        result = await search_tool(
            {"type": "event", "gql": f'type.string = "{name}"', "max_results": 1}
        )

        assert result[0].text.splitlines()[0] == "Found 2 events (showing 1):"


class TestListTagsPaging:
    """list_tags sends page and reports what the page left out."""

    @pytest.mark.asyncio
    async def test_page_cut_reports_total_and_next_page(self):
        for suffix in ("A", "B", "C"):
            await UPSERT_HANDLERS["tag"]({"name": f"MCP_TEST_Page_{suffix}"})

        rows = await get_client().make_api_call(
            api_call=collection_call("tag"),
            params=TagSearchParams(pagesize=2),
            tree_id=get_settings().gramps_tree_id,
        )
        assert len(rows) == 2

        result = await list_tags_tool({"pagesize": 2})
        text = result[0].text
        assert "(showing 2)" in text
        assert "page 2 and pagesize 2" in text
