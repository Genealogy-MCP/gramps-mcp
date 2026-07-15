# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for the shared timeline event pre-fetch/resolve helpers."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.gramps_mcp.handlers.timeline_events import (
    prefetch_timeline_events,
    resolve_event_date,
)

TREE_ID = "tree1"


class TestPrefetchTimelineEvents:
    """prefetch_timeline_events fans out bounded, deduped GET_EVENT calls."""

    @pytest.mark.asyncio
    async def test_empty_timeline_makes_no_calls(self):
        client = AsyncMock()
        result = await prefetch_timeline_events(client, TREE_ID, [])
        assert result == {}
        client.make_api_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_entries_without_handles_make_no_calls(self):
        client = AsyncMock()
        timeline = [{"type": "Birth"}, "not-a-dict", {"handle": ""}]
        result = await prefetch_timeline_events(client, TREE_ID, timeline)
        assert result == {}
        client.make_api_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_repeated_handle_fetched_once(self):
        fetches = 0

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            nonlocal fetches
            fetches += 1
            return {"handle": handle, "date": {}}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        timeline = [{"handle": "dup"}, {"handle": "dup"}, {"handle": "other"}]
        result = await prefetch_timeline_events(client, TREE_ID, timeline)
        assert fetches == 2
        assert set(result.keys()) == {"dup", "other"}

    @pytest.mark.asyncio
    async def test_distinct_events_overlap_in_flight(self):
        active = 0
        peak = 0

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {"handle": handle}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        timeline = [{"handle": f"evt_{i}"} for i in range(4)]
        await prefetch_timeline_events(client, TREE_ID, timeline)
        assert peak >= 2

    @pytest.mark.asyncio
    async def test_failed_fetch_captured_not_raised(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            if handle == "boom":
                raise ValueError("upstream 500")
            return {"handle": handle}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        timeline = [{"handle": "ok"}, {"handle": "boom"}]
        result = await prefetch_timeline_events(client, TREE_ID, timeline)
        assert result["ok"] == {"handle": "ok"}
        assert isinstance(result["boom"], ValueError)


class TestResolveEventDate:
    """resolve_event_date reproduces the tolerant serial fallback exactly."""

    def test_no_handle_returns_unknown(self):
        assert resolve_event_date(None, {"date": "1850"}, "") == (None, "date unknown")

    def test_exception_falls_back_to_timeline_date(self):
        assert resolve_event_date(ValueError("x"), {"date": "circa 1850"}, "h") == (
            None,
            "circa 1850",
        )

    def test_none_result_falls_back_but_skips_citations(self):
        assert resolve_event_date(None, {"date": "raw"}, "h") == (None, "raw")

    def test_success_formats_date(self):
        event = {"date": {"dateval": [1, 5, 1850, False]}}
        assert resolve_event_date(event, {}, "h") == (event, "01 May 1850")

    def test_malformed_date_falls_back_but_keeps_event_data(self):
        """A format_date failure keeps event_data (citations render) + raw date."""
        event = {"date": "unparseable-not-a-dict"}
        event_data, event_date = resolve_event_date(event, {"date": "1850"}, "h")
        assert event_data is event
        assert event_date == "1850"
