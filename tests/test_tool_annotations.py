"""
Tests for Sprint B — tool annotations, settings caching, dispatch patterns,
and error message context.

Unit tests only — no network required.
"""

import pytest

from src.gramps_mcp.config import get_settings
from src.gramps_mcp.server import (
    _DELETE_ANNOTATIONS,
    _READ_ANNOTATIONS,
    _WRITE_ANNOTATIONS,
    TOOL_REGISTRY,
)
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
    """MCP-5: Every tool must have annotations with correct hints."""

    def test_all_tools_have_annotations(self):
        """Every registered tool must carry an 'annotations' key."""
        missing = [
            name
            for name, config in TOOL_REGISTRY.items()
            if "annotations" not in config or config["annotations"] is None
        ]
        assert missing == [], f"Tools missing annotations: {missing}"

    def test_read_tools_are_read_only(self):
        """Read-only tools must set readOnlyHint=True."""
        for name in READ_TOOLS:
            ann = TOOL_REGISTRY[name]["annotations"]
            assert ann.readOnlyHint is True, f"{name} should be readOnlyHint=True"
            assert ann.destructiveHint is False, f"{name} should not be destructive"

    def test_write_tools_are_not_read_only(self):
        """Create/update tools must NOT be readOnlyHint."""
        for name in WRITE_TOOLS:
            ann = TOOL_REGISTRY[name]["annotations"]
            assert ann.readOnlyHint is False, f"{name} should be readOnlyHint=False"
            assert ann.destructiveHint is False, f"{name} should not be destructive"

    def test_delete_tool_is_destructive(self):
        """delete_type must be destructiveHint=True."""
        for name in DELETE_TOOLS:
            ann = TOOL_REGISTRY[name]["annotations"]
            assert ann.destructiveHint is True, f"{name} should be destructive"
            assert ann.readOnlyHint is False, f"{name} should not be read-only"

    def test_all_tools_are_open_world(self):
        """All tools interact with external Gramps API — openWorldHint=True."""
        for name, config in TOOL_REGISTRY.items():
            ann = config["annotations"]
            assert ann.openWorldHint is True, f"{name} should be openWorldHint=True"

    def test_all_tools_are_idempotent(self):
        """All tools should be idempotentHint=True (PUT semantics, safe retries)."""
        for name, config in TOOL_REGISTRY.items():
            ann = config["annotations"]
            assert ann.idempotentHint is True, f"{name} should be idempotentHint=True"

    def test_annotation_presets_are_distinct(self):
        """The three preset objects must differ on their key hints."""
        assert _READ_ANNOTATIONS.readOnlyHint is True
        assert _WRITE_ANNOTATIONS.readOnlyHint is False
        assert _DELETE_ANNOTATIONS.destructiveHint is True
        assert _WRITE_ANNOTATIONS.destructiveHint is False

    def test_tool_categories_cover_all_tools(self):
        """READ + WRITE + DELETE must equal the full TOOL_REGISTRY key set."""
        all_categorized = READ_TOOLS | WRITE_TOOLS | DELETE_TOOLS
        all_registered = set(TOOL_REGISTRY.keys())
        assert all_categorized == all_registered, (
            f"Uncategorized tools: {all_registered - all_categorized}"
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

    def test_find_dispatch_covers_all_entity_types(self):
        """_SEARCH_TOOL_DISPATCH must have an entry for every EntityType value."""
        from src.gramps_mcp.models.parameters.simple_params import EntityType

        expected = {e.value for e in EntityType}
        actual = set(_SEARCH_TOOL_DISPATCH.keys())
        assert actual == expected, f"Missing dispatch entries: {expected - actual}"

    def test_find_dispatch_values_are_callable(self):
        """Every dispatch value must be callable."""
        for name, func in _SEARCH_TOOL_DISPATCH.items():
            assert callable(func), f"Dispatch entry '{name}' is not callable"

    def test_formatter_dispatch_covers_all_entity_types(self):
        """FORMATTER_DISPATCH must have an entry for every EntityType value."""
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
