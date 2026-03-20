"""
Integration tests for analysis tools using real Gramps Web API.

Tests get_descendants, get_ancestors, and get_recent_changes tools.
These tests require a working Gramps Web API instance with valid credentials.
"""

import pytest
from dotenv import load_dotenv
from mcp.types import TextContent

from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.analysis import (
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
)

# Load environment variables from .env file
load_dotenv()

pytestmark = pytest.mark.integration

# Test constants
TEST_MAX_GENERATIONS = 2
INVALID_GRAMPS_ID = "INVALID99999"


class TestGetDescendantsTool:
    """Test get_descendants_tool functionality."""

    @pytest.mark.asyncio
    async def test_get_descendants_real_api(self):
        """Test get_descendants_tool with real API.

        Uses I0044 (Lewis Anderson Garner) with max_generations=2 to keep the
        report small and fast. Default max_generations logic is unit-tested.
        """
        result = await get_descendants_tool(
            {"gramps_id": "I0044", "max_generations": TEST_MAX_GENERATIONS}
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        text = result[0].text
        assert len(text.strip()) > 50
        assert "report generated successfully" not in text.lower()
        assert any(
            keyword in text.lower()
            for keyword in [
                "person",
                "name",
                "birth",
                "death",
                "descendant",
                "child",
                "family",
            ]
        )

    @pytest.mark.asyncio
    async def test_get_descendants_invalid_gramps_id(self):
        """Test descendants retrieval with invalid gramps ID raises McpToolError."""

        with pytest.raises(McpToolError):
            await get_descendants_tool({"gramps_id": INVALID_GRAMPS_ID})


class TestGetAncestorsTool:
    """Test get_ancestors_tool functionality."""

    @pytest.mark.asyncio
    async def test_get_ancestors_real_api(self):
        """Test get_ancestors_tool with real API.

        Uses I0001 with max_generations=2 to keep the report small and fast.
        Default max_generations logic is unit-tested.
        """
        result = await get_ancestors_tool(
            {"gramps_id": "I0001", "max_generations": TEST_MAX_GENERATIONS}
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        text = result[0].text
        assert len(text.strip()) > 50
        assert "report generated successfully" not in text.lower()
        assert "generation" in text.lower()

    @pytest.mark.asyncio
    async def test_get_ancestors_invalid_gramps_id(self):
        """Test ancestors retrieval with invalid gramps ID raises McpToolError."""

        with pytest.raises(McpToolError):
            await get_ancestors_tool({"gramps_id": INVALID_GRAMPS_ID})


class TestGetRecentChangesTool:
    """Test get_recent_changes_tool functionality."""

    @pytest.mark.asyncio
    async def test_get_recent_changes_real_api(self):
        """Test get_recent_changes_tool with real API."""

        result = await get_recent_changes_tool({"page": 1, "pagesize": 10})

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        text = result[0].text
        print("\n=== RECENT CHANGES TEST OUTPUT ===")
        print(f"Result: {text}")
        print("=" * 50)

        assert "recent changes" in text.lower()
        # With populated tree, expect actual recent changes data
        assert "found" in text.lower() and "no recent changes found" not in text.lower()

        # Count the number of transaction entries (each starts with "• **")
        transaction_count = text.count("• **")
        assert 1 <= transaction_count <= 10, (
            f"Expected 1-10 transactions but got {transaction_count}"
        )

        # Should show gramps_id or (deleted) annotation for deleted objects
        if "Objects changed:" in text:
            import re

            has_gramps_id = re.search(r"[A-Z]\d{4}", text)
            has_deleted = "(deleted)" in text
            assert has_gramps_id or has_deleted, (
                "Should show gramps IDs or (deleted) annotation"
            )


class TestGetTreeInfoTool:
    """Test get_tree_stats_tool functionality."""

    @pytest.mark.asyncio
    async def test_get_tree_info_real_api(self):
        """Test get_tree_stats_tool with real API."""

        result = await get_tree_stats_tool({"include_statistics": True})

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        text = result[0].text
        print("\n=== TREE INFO TEST OUTPUT ===")
        print(f"Result: {text}")
        print("=" * 50)

        # Should contain tree information
        assert "Family Tree:" in text
        assert "Tree ID:" in text

        # Should contain statistics (not "Statistics not available")
        assert "Statistics not available" not in text

        # Should contain actual counts
        assert "People:" in text or "people_count" in text.lower()


# Note: AnalysisClient tests removed as we now use unified GrampsWebAPIClient
