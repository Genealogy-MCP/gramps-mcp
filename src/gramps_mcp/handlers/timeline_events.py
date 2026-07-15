# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Shared timeline event pre-fetch and date resolution.

Both the person and family detail renders walk a timeline and need one
`GET_EVENT?extend=all` per referenced event. Fetching them serially is an
MCP-22 N+1 violation, so this module centralizes the bounded concurrent
pre-fetch (`prefetch_timeline_events`) and the tolerant per-entry date
resolution (`resolve_event_date`) that both handlers reuse verbatim.
"""

import logging

from ..models.api_calls import ApiCalls
from ..utils import gather_bounded
from .date_handler import format_date

logger = logging.getLogger(__name__)

# Ceiling on concurrent GET_EVENT fetches when rendering a timeline, so a
# long-timeline entity does not flood the shared httpx pool or the upstream
# Gramps Web instance (MCP-22 bounded fan-out).
TIMELINE_FETCH_CONCURRENCY = 8


async def prefetch_timeline_events(client, tree_id: str, timeline_data: list) -> dict:
    """
    Concurrently fetch every event referenced by a timeline.

    Args:
        client: Gramps API client instance.
        tree_id (str): Family tree identifier.
        timeline_data (list): Raw timeline entries (list of dicts).

    Returns:
        dict: Maps each event handle to its `GET_EVENT?extend=all` result, or to
        the Exception raised for that handle (captured via
        `return_exceptions=True` so one failed fetch never aborts the render).
        Unique handles only -- a handle appearing in several entries is fetched
        once and its result reused, keeping output unchanged.
    """
    unique_handles = list(
        dict.fromkeys(
            te.get("handle", "")
            for te in timeline_data
            if isinstance(te, dict) and te.get("handle")
        )
    )
    if not unique_handles:
        return {}

    fetch_results = await gather_bounded(
        TIMELINE_FETCH_CONCURRENCY,
        [
            client.make_api_call(
                ApiCalls.GET_EVENT,
                tree_id=tree_id,
                handle=event_handle,
                params={"extend": "all"},
            )
            for event_handle in unique_handles
        ],
        return_exceptions=True,
    )
    return dict(zip(unique_handles, fetch_results))


def resolve_event_date(
    fetched_event: dict | Exception | None,
    timeline_event: dict,
    event_handle: str,
) -> tuple[dict | None, str]:
    """
    Resolve (event_data, event_date) for one timeline entry, preserving the
    original serial loop's tolerant fallback exactly.

    Args:
        fetched_event: The pre-fetched GET_EVENT result, an Exception if the
            fetch failed (from `prefetch_timeline_events`), or None.
        timeline_event (dict): The raw timeline entry (holds the fallback date).
        event_handle (str): The event handle (empty string if absent).

    Returns:
        tuple: (event_data or None, formatted-or-fallback date string). A None
        event_data signals to the caller that citations must be skipped, matching
        the original behavior when the event fetch failed.
    """
    if not event_handle:
        return None, "date unknown"
    if isinstance(fetched_event, Exception):
        logger.warning(f"Failed to fetch event {event_handle}: {fetched_event}")
        return None, timeline_event.get("date", "date unknown")
    if fetched_event is None:
        return None, timeline_event.get("date", "date unknown")
    try:
        return fetched_event, format_date(fetched_event.get("date", {}))
    except Exception as e:
        logger.warning(f"Failed to fetch event {event_handle}: {e}")
        return fetched_event, timeline_event.get("date", "date unknown")
