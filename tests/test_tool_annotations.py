"""
Tests for Sprint B — tool annotations, settings caching, dispatch patterns,
and error message context.

Unit tests only — no network required.
"""

import pytest

from src.gramps_mcp.config import get_settings
from src.gramps_mcp.operations import OPERATION_REGISTRY
from src.gramps_mcp.tools._errors import McpToolError, raise_tool_error
from src.gramps_mcp.tools.search_basic import _SEARCH_TOOL_DISPATCH, FORMATTER_DISPATCH

# ---------------------------------------------------------------------------
# Tool annotation categories
# ---------------------------------------------------------------------------

READ_TOOLS = {
    "search",
    "search_text",
    "list_tags",
    "get",
    "get_tree_stats",
    "get_descendants",
    "get_ancestors",
    "get_recent_changes",
}

WRITE_TOOLS = {
    "upsert_person",
    "upsert_family",
    "upsert_event",
    "upsert_place",
    "upsert_source",
    "upsert_citation",
    "upsert_note",
    "upsert_media",
    "upsert_repository",
    "upsert_tag",
}

DELETE_TOOLS = {"delete"}


class TestToolAnnotations:
    """MCP-5: Every operation must have correct behavioral flags."""

    def test_read_operations_are_read_only(self):
        """Read-only operations must have read_only=True."""
        for name in READ_TOOLS:
            entry = OPERATION_REGISTRY[name]
            assert entry.read_only is True, f"{name} should be read_only"
            assert entry.destructive is False, f"{name} should not be destructive"

    def test_write_operations_are_not_read_only(self):
        """Create/update operations must NOT be read_only."""
        for name in WRITE_TOOLS:
            entry = OPERATION_REGISTRY[name]
            assert entry.read_only is False, f"{name} should be read_only=False"
            assert entry.destructive is False, f"{name} should not be destructive"

    def test_delete_operation_is_destructive(self):
        """delete must be destructive=True."""
        for name in DELETE_TOOLS:
            entry = OPERATION_REGISTRY[name]
            assert entry.destructive is True, f"{name} should be destructive"
            assert entry.read_only is False, f"{name} should not be read-only"

    def test_tool_categories_cover_all_operations(self):
        """READ + WRITE + DELETE must equal the full OPERATION_REGISTRY key set."""
        all_categorized = READ_TOOLS | WRITE_TOOLS | DELETE_TOOLS
        all_registered = set(OPERATION_REGISTRY.keys())
        assert all_categorized == all_registered, (
            f"Uncategorized operations: {all_registered - all_categorized}"
        )


class TestSettingsCache:
    """MCP-23: get_settings() must be cached."""

    def test_settings_identity(self):
        """Repeated calls must return the exact same object (lru_cache)."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_returns_valid_object(self):
        """Cached settings must still be a valid Settings instance."""
        s = get_settings()
        assert hasattr(s, "gramps_api_url")
        assert hasattr(s, "gramps_username")


class TestSettingsValidation:
    """Config must fail loudly when required env vars are missing."""

    def test_missing_env_vars_raises(self, monkeypatch):
        """get_settings() raises ValueError listing missing vars."""
        # Clear the lru_cache so get_settings() re-reads env
        get_settings.cache_clear()
        try:
            monkeypatch.delenv("GRAMPS_API_URL", raising=False)
            monkeypatch.delenv("GRAMPS_USERNAME", raising=False)
            monkeypatch.delenv("GRAMPS_PASSWORD", raising=False)

            with pytest.raises(ValueError, match="GRAMPS_API_URL"):
                get_settings()
        finally:
            # Restore cache so other tests see cached settings
            get_settings.cache_clear()


class TestDispatchPatterns:
    """MCP-18: No globals() dispatch; use explicit dicts."""

    def test_find_dispatch_covers_all_searchable_entity_types(self):
        """_SEARCH_TOOL_DISPATCH must cover all EntityType values.

        EntityType excludes TAG by design — tags use list_tags, not GQL search.
        """
        from src.gramps_mcp.models.parameters.simple_params import EntityType

        expected = {e.value for e in EntityType}
        actual = set(_SEARCH_TOOL_DISPATCH.keys())
        assert actual == expected, f"Missing dispatch entries: {expected - actual}"

    def test_find_dispatch_values_are_callable(self):
        """Every dispatch value must be callable."""
        for name, func in _SEARCH_TOOL_DISPATCH.items():
            assert callable(func), f"Dispatch entry '{name}' is not callable"

    def test_formatter_dispatch_covers_all_searchable_entity_types(self):
        """FORMATTER_DISPATCH must cover all EntityType values.

        EntityType excludes TAG by design — tags use list_tags, not the
        generic search/format pipeline.
        """
        from src.gramps_mcp.models.parameters.simple_params import EntityType

        expected = {e.value for e in EntityType}
        actual = set(FORMATTER_DISPATCH.keys())
        assert actual == expected, f"Missing formatter entries: {expected - actual}"

    def test_formatter_dispatch_values_are_callable(self):
        """Every formatter must be callable."""
        for name, func in FORMATTER_DISPATCH.items():
            assert callable(func), f"Formatter '{name}' is not callable"


class TestErrorContext:
    """MCP-9: Error messages must include entity context when available."""

    def test_error_with_entity_context(self):
        """raise_tool_error with entity_type+identifier appends context."""
        with pytest.raises(McpToolError, match=r"person.*abc123"):
            raise_tool_error(
                ValueError("not found"),
                "test op",
                entity_type="person",
                identifier="abc123",
            )

    def test_error_with_identifier_only(self):
        """raise_tool_error with only identifier still appends context."""
        with pytest.raises(McpToolError, match=r"id.*xyz"):
            raise_tool_error(
                ValueError("not found"),
                "test op",
                identifier="xyz",
            )

    def test_error_without_context_unchanged(self):
        """raise_tool_error without context keeps original message."""
        with pytest.raises(McpToolError, match="Unexpected error during test op"):
            raise_tool_error(ValueError("boom"), "test op")

    def test_gramps_api_error_preserves_message(self):
        """GrampsAPIError message is used directly."""
        from src.gramps_mcp.client import GrampsAPIError

        with pytest.raises(McpToolError, match="API went wrong"):
            raise_tool_error(GrampsAPIError("API went wrong"), "test op")

    def test_mcp_tool_error_preserves_message(self):
        """McpToolError message is forwarded."""
        with pytest.raises(McpToolError, match="already an mcp error"):
            raise_tool_error(McpToolError("already an mcp error"), "test op")
