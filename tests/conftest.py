"""
Shared test fixtures for Gramps MCP integration tests.

Provides HandleRegistry for tracking created entities and cleaning them up
after test sessions, plus a sweep function for removing orphaned MCP_TEST_
artifacts from previous interrupted runs.
"""

import asyncio
import atexit
import logging
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from unittest.mock import AsyncMock

import pytest

from src.gramps_mcp.auth import AuthManager
from src.gramps_mcp.client import GrampsAPIError, GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools.data_management_delete import DELETE_API_CALLS

# ---------------------------------------------------------------------------
# Default test instance — local Docker Gramps Web on port 5055.
# Applied before test collection so get_settings() never fails.
# ---------------------------------------------------------------------------
_DEFAULT_API_URL = "http://localhost:5055"
_DEFAULT_USERNAME = "owner"
_DEFAULT_PASSWORD = "owner"


def _is_docker_reachable(url: str) -> bool:
    """Check if the local Gramps Web Docker instance is responding.

    Args:
        url: Base URL to probe (e.g. http://localhost:5055).

    Returns:
        True if the service responds with HTTP 200.
    """
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"{url}/", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def pytest_configure(config: pytest.Config) -> None:
    """Set default env vars before any test collection or imports.

    Uses setdefault so a developer's .env takes precedence.
    """
    os.environ.setdefault("GRAMPS_API_URL", _DEFAULT_API_URL)
    os.environ.setdefault("GRAMPS_USERNAME", _DEFAULT_USERNAME)
    os.environ.setdefault("GRAMPS_PASSWORD", _DEFAULT_PASSWORD)

    target = os.environ["GRAMPS_API_URL"]
    is_default = target == _DEFAULT_API_URL
    suffix = " (local Docker defaults)" if is_default else ""
    print(f"\nGramps MCP Tests — targeting: {target}{suffix}\n")


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Auto-skip integration tests when Docker is unreachable.

    In CI (REQUIRE_INTEGRATION=1), integration tests FAIL instead of skipping.
    Locally (default), they skip with a warning if Docker is down.
    """
    require = os.environ.get("REQUIRE_INTEGRATION", "").strip()
    target = os.environ.get("GRAMPS_API_URL", _DEFAULT_API_URL)

    if _is_docker_reachable(target):
        return

    if require == "1":
        pytest.fail(
            f"REQUIRE_INTEGRATION=1 but Gramps Web at {target} is unreachable. "
            "Start Docker with: make docker-up && make docker-seed",
            pytrace=False,
        )

    skip_marker = pytest.mark.skip(
        reason=f"Gramps Web at {target} is unreachable (run: make test-integration)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(autouse=True)
def reset_auth_singleton():
    """Reset AuthManager singleton before and after each test.

    Prevents stale token state from leaking between tests across all files.
    """
    AuthManager.reset_instance()
    yield
    AuthManager.reset_instance()


logger = logging.getLogger(__name__)

TEST_PREFIX = "MCP_TEST_"

# Deletion order respects referential integrity: entities that reference others
# are deleted first. Families reference people/events, people reference events,
# citations reference sources, sources reference repositories.
DELETION_PRIORITY: List[str] = [
    "family",
    "person",
    "event",
    "citation",
    "source",
    "repository",
    "place",
    "media",
    "note",
    "tag",
]


# GQL filters per entity type for finding MCP_TEST_ prefixed records.
# Note: notes are excluded because Gramps Web's GQL engine returns 500
# on any note query (even trivial ones like `private = false`). Notes are
# swept via client-side filtering in _sweep_notes_fallback() instead.
_SWEEP_GQL_FILTERS: Dict[str, str] = {
    "person": f'primary_name.first_name ~ "{TEST_PREFIX}"',
    "event": f'description ~ "{TEST_PREFIX}"',
    "citation": f'page ~ "{TEST_PREFIX}"',
    "source": f'title ~ "{TEST_PREFIX}"',
    "repository": f'name ~ "{TEST_PREFIX}"',
    "place": f'name.value ~ "{TEST_PREFIX}"',
    "media": f'desc ~ "{TEST_PREFIX}"',
}

# API list endpoints keyed by entity type.
_LIST_ENDPOINTS: Dict[str, ApiCalls] = {
    "person": ApiCalls.GET_PEOPLE,
    "family": ApiCalls.GET_FAMILIES,
    "event": ApiCalls.GET_EVENTS,
    "place": ApiCalls.GET_PLACES,
    "source": ApiCalls.GET_SOURCES,
    "citation": ApiCalls.GET_CITATIONS,
    "note": ApiCalls.GET_NOTES,
    "media": ApiCalls.GET_MEDIA,
    "repository": ApiCalls.GET_REPOSITORIES,
}


class HandleRegistry:
    """Tracks created entity handles for cleanup after test sessions.

    Thread-safe via set deduplication. Handles are deleted in priority order
    (reverse dependency) and newest-first within each type.
    """

    def __init__(self) -> None:
        self._tracked: Dict[str, List[str]] = defaultdict(list)
        self._seen: Set[Tuple[str, str]] = set()
        self._cleaned = False

    def track(self, entity_type: str, handle: str) -> None:
        """Register a handle for cleanup.

        Args:
            entity_type: Gramps entity type (person, family, event, etc.)
            handle: Entity handle string.
        """
        key = (entity_type, handle)
        if key not in self._seen:
            self._seen.add(key)
            self._tracked[entity_type].append(handle)
            logger.info(f"Tracked {entity_type} [{handle}] for cleanup")

    def track_from_response(
        self, entity_type: str, response_text: str
    ) -> Optional[str]:
        """Extract handle from tool response text and track it.

        Args:
            entity_type: Gramps entity type.
            response_text: Text output from a create_*_tool call.

        Returns:
            Extracted handle, or None if no handle found.
        """
        match = re.search(r"\[([a-f0-9]+)\]", response_text)
        if match:
            handle = match.group(1)
            self.track(entity_type, handle)
            return handle
        return None

    async def cleanup_all(self) -> None:
        """Delete all tracked handles in priority order.

        Resilient to failures: logs errors and continues. Tolerates 404s
        (entity already deleted). Guards against double-cleanup.
        """
        if self._cleaned:
            return
        self._cleaned = True

        total = sum(len(handles) for handles in self._tracked.values())
        if total == 0:
            return

        logger.info(f"Cleaning up {total} tracked test entities...")

        client = GrampsWebAPIClient()
        settings = get_settings()
        tree_id = settings.gramps_tree_id

        try:
            for entity_type in DELETION_PRIORITY:
                handles = self._tracked.get(entity_type, [])
                # Reverse: newest first (place children before parents, etc.)
                for handle in reversed(handles):
                    api_call = DELETE_API_CALLS.get(entity_type)
                    if not api_call:
                        if entity_type == "tag":
                            try:
                                await client.bulk_delete(
                                    items=[{"_class": "Tag", "handle": handle}],
                                    tree_id=tree_id,
                                )
                                logger.info(
                                    f"Deleted {entity_type} [{handle}] via bulk endpoint"
                                )
                            except Exception as e:
                                if "404" in str(e) or "not found" in str(e).lower():
                                    logger.info(
                                        f"Already gone: {entity_type} [{handle}]"
                                    )
                                else:
                                    logger.warning(
                                        f"Failed to delete {entity_type} [{handle}]: {e}"
                                    )
                            continue
                        logger.warning(f"No delete API call for type '{entity_type}'")
                        continue
                    try:
                        await client.make_api_call(
                            api_call=api_call,
                            tree_id=tree_id,
                            handle=handle,
                        )
                        logger.info(f"Deleted {entity_type} [{handle}]")
                    except GrampsAPIError as e:
                        if "404" in str(e) or "not found" in str(e).lower():
                            logger.info(f"Already gone: {entity_type} [{handle}]")
                        else:
                            logger.warning(
                                f"Failed to delete {entity_type} [{handle}]: {e}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Unexpected error deleting {entity_type} [{handle}]: {e}"
                        )
        finally:
            await client.close()
            self._tracked.clear()
            self._seen.clear()


async def _sweep_notes_fallback(client: GrampsWebAPIClient, tree_id: str) -> List[str]:
    """List all notes and filter client-side for MCP_TEST_ prefix.

    The Gramps Web demo server's GQL engine is broken for notes (returns 500
    on any query). This fallback lists all notes and checks text content
    client-side.

    Args:
        client: Authenticated API client.
        tree_id: Gramps tree identifier.

    Returns:
        List of note handles matching the test prefix.
    """
    try:
        response = await client.make_api_call(
            api_call=ApiCalls.GET_NOTES,
            tree_id=tree_id,
            params={"pagesize": 200},
        )
        if not isinstance(response, list):
            return []
        handles = []
        for note in response:
            if not isinstance(note, dict):
                continue
            text = note.get("text", "")
            # StyledText wraps the string in a dict
            if isinstance(text, dict):
                text = text.get("string", "")
            if isinstance(text, str) and TEST_PREFIX in text:
                handle = note.get("handle")
                if handle:
                    handles.append(handle)
        return handles
    except Exception as e:
        logger.warning(f"Sweep notes fallback failed: {e}")
        return []


async def _paginated_gql_query(
    client: GrampsWebAPIClient,
    api_call: ApiCalls,
    tree_id: str,
    gql: str,
    pagesize: int = 100,
) -> List[dict]:
    """Fetch all pages of a GQL-filtered list endpoint.

    Loops with incrementing page parameter until the server returns fewer
    results than pagesize (indicating the last page).

    Args:
        client: Authenticated API client.
        api_call: List endpoint to query.
        tree_id: Gramps tree identifier.
        gql: GQL filter expression.
        pagesize: Items per page.

    Returns:
        Aggregated list of entity dicts across all pages.
    """
    all_results: List[dict] = []
    page = 1
    while True:
        response = await client.make_api_call(
            api_call=api_call,
            tree_id=tree_id,
            params={"gql": gql, "pagesize": pagesize, "page": page},
        )
        if not isinstance(response, list) or not response:
            break
        all_results.extend(item for item in response if isinstance(item, dict))
        if len(response) < pagesize:
            break
        page += 1
    return all_results


async def sweep_test_artifacts() -> int:
    """Find and delete MCP_TEST_ prefixed entities from previous runs.

    Uses GQL queries per entity type to locate orphaned test data.
    Notes use a client-side fallback since the server's GQL for notes is broken.
    Families are discovered via person→family_list cascade (families have no
    searchable text field).
    Returns the count of successfully deleted entities.
    """
    logger.info(f"Sweeping leftover {TEST_PREFIX} artifacts...")

    client = GrampsWebAPIClient()
    settings = get_settings()
    tree_id = settings.gramps_tree_id
    deleted_count = 0

    try:
        # Collect handles to delete, grouped by type
        to_delete: Dict[str, List[str]] = defaultdict(list)
        # Keep full person objects for family cascade
        test_persons: List[dict] = []

        for entity_type, gql_filter in _SWEEP_GQL_FILTERS.items():
            api_call = _LIST_ENDPOINTS.get(entity_type)
            if not api_call:
                continue
            try:
                results = await _paginated_gql_query(
                    client, api_call, tree_id, gql_filter
                )
                for item in results:
                    handle = item.get("handle")
                    if handle:
                        to_delete[entity_type].append(handle)
                    if entity_type == "person":
                        test_persons.append(item)
            except Exception as e:
                logger.warning(f"Sweep search failed for {entity_type}: {e}")

        # Person→family cascade: extract family_list handles from test persons
        for person in test_persons:
            for family_handle in person.get("family_list", []):
                if family_handle not in to_delete["family"]:
                    to_delete["family"].append(family_handle)

        # Notes: client-side fallback (server GQL broken for notes)
        note_handles = await _sweep_notes_fallback(client, tree_id)
        to_delete["note"].extend(note_handles)

        # Also search tags by name (tags don't support GQL on all fields)
        try:
            tags_response = await client.make_api_call(
                api_call=ApiCalls.GET_TAGS,
                tree_id=tree_id,
            )
            if isinstance(tags_response, list):
                for tag in tags_response:
                    if isinstance(tag, dict):
                        name = tag.get("name", "")
                        handle = tag.get("handle")
                        if name.startswith(TEST_PREFIX) and handle:
                            to_delete["tag"].append(handle)
        except Exception as e:
            logger.warning(f"Sweep search failed for tags: {e}")

        total = sum(len(h) for h in to_delete.values())
        if total == 0:
            logger.info("No leftover test artifacts found.")
            return 0

        logger.info(f"Found {total} leftover artifacts to sweep.")

        # Delete in priority order
        for entity_type in DELETION_PRIORITY:
            handles = to_delete.get(entity_type, [])
            for handle in handles:
                api_call = DELETE_API_CALLS.get(entity_type)
                if not api_call:
                    continue
                try:
                    await client.make_api_call(
                        api_call=api_call,
                        tree_id=tree_id,
                        handle=handle,
                    )
                    deleted_count += 1
                    logger.info(f"Swept {entity_type} [{handle}]")
                except Exception as e:
                    logger.warning(f"Failed to sweep {entity_type} [{handle}]: {e}")

        # Tags use bulk delete endpoint (API 3.x removed DELETE /tags/{handle})
        for handle in to_delete.get("tag", []):
            try:
                await client.bulk_delete(
                    items=[{"_class": "Tag", "handle": handle}], tree_id=tree_id
                )
                deleted_count += 1
                logger.info(f"Swept tag [{handle}]")
            except Exception as e:
                logger.warning(f"Failed to sweep tag [{handle}]: {e}")

    finally:
        await client.close()

    logger.info(f"Sweep complete: {deleted_count}/{total} entities deleted.")
    return deleted_count


# Module-level registry for atexit (needed for Ctrl+C recovery)
_atexit_registry: Optional[HandleRegistry] = None


def _atexit_cleanup() -> None:
    """Atexit handler that runs cleanup synchronously."""
    if _atexit_registry is not None:
        try:
            asyncio.run(_atexit_registry.cleanup_all())
        except Exception as e:
            # Reason: atexit handlers must not raise — Python ignores them
            # but prints ugly tracebacks during shutdown
            logger.warning(f"Atexit cleanup error: {e}")


@pytest.fixture(scope="session")
async def cleanup_registry():
    """Session-scoped fixture providing a HandleRegistry with atexit safety.

    - Sweeps leftover MCP_TEST_ artifacts from previous runs at session start
    - Tracks all handles created during the session
    - Deletes tracked handles at session end (pytest teardown)
    - Also registered via atexit for Ctrl+C / crash recovery
    """
    global _atexit_registry

    registry = HandleRegistry()
    _atexit_registry = registry
    atexit.register(_atexit_cleanup)

    # Sweep leftovers from previous interrupted runs
    try:
        await sweep_test_artifacts()
    except Exception as e:
        logger.warning(f"Pre-test sweep failed (non-fatal): {e}")

    yield registry

    # Normal teardown path
    await registry.cleanup_all()


def pytest_sessionfinish(session, exitstatus):
    """Sweep MCP_TEST_ artifacts after all tests and fixture teardowns complete.

    This is the safety net that runs unconditionally — even when:
    - Only unit tests ran (cleanup_registry fixture never triggered)
    - Fixture cleanup missed some entities (server errors)
    - Tests created entities without using the registry

    Short-circuits when Docker is unreachable to avoid a 3s timeout
    penalty on unit-only runs.
    """
    target = os.environ.get("GRAMPS_API_URL", _DEFAULT_API_URL)
    if not _is_docker_reachable(target):
        return

    try:
        asyncio.run(sweep_test_artifacts())
    except Exception as e:
        # Reason: non-fatal — cleanup failure must not mask test results
        logger.warning(f"Post-test sweep failed (non-fatal): {e}")


def _mock_client(responses):
    """Create a mock client returning predefined responses by API call name.

    Keys should be enum names like "GET_NOTE", "GET_SOURCE", etc.
    Values can be a dict (same response every time) or a list of dicts
    (returns each in sequence, repeating the last for extra calls).
    """
    client = AsyncMock()
    call_count = {}

    async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
        key = api_call.name if hasattr(api_call, "name") else str(api_call)
        call_count.setdefault(key, 0)
        if key in responses:
            val = responses[key]
            if isinstance(val, list):
                idx = min(call_count[key], len(val) - 1)
                call_count[key] += 1
                return val[idx]
            return val
        return {}

    client.make_api_call = AsyncMock(side_effect=mock_api_call)
    return client
