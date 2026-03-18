"""Unit tests for analysis formatting functions.

Tests _format_recent_changes with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest

from src.gramps_mcp.tools.analysis import _format_recent_changes

TREE_ID = "test-tree"


class TestFormatRecentChanges:
    """Test _format_recent_changes formatting logic."""

    @pytest.mark.asyncio
    async def test_empty_transactions(self):
        """Test with no transactions returns 'No recent changes found.'."""
        client = AsyncMock()
        result = await _format_recent_changes([], client, TREE_ID)
        assert result == "No recent changes found."

    @pytest.mark.asyncio
    async def test_deletion_shows_deleted_annotation(self):
        """Test that unresolved handles (deleted objects) get annotated."""
        client = AsyncMock()
        # Simulate 404 -- get_gramps_id_from_handle returns the raw handle
        client.make_api_call = AsyncMock(side_effect=Exception("404 Not Found"))

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Delete person",
                "connection": {"user": {"name": "test"}},
                "changes": [
                    {
                        "obj_class": "Person",
                        "obj_handle": "abcdef1234567890abcdef12",
                    }
                ],
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "(deleted)" in result
        assert "abcdef123456..." in result

    @pytest.mark.asyncio
    async def test_numeric_obj_class_resolved(self):
        """Test that numeric obj_class codes are resolved to names."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "P0001"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Add place",
                "connection": {"user": {"name": "test"}},
                "changes": [
                    {
                        "obj_class": 5,
                        "obj_handle": "abc123",
                    }
                ],
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "Place" in result
        assert "P0001" in result
        # Should NOT show the raw numeric code
        assert "- 5:" not in result

    @pytest.mark.asyncio
    async def test_resolved_gramps_id_shown(self):
        """Test that resolved gramps IDs are shown directly."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I0042"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Edit person",
                "connection": {"user": {"name": "admin"}},
                "changes": [
                    {
                        "obj_class": "Person",
                        "obj_handle": "validhandle123",
                    }
                ],
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "I0042" in result
        assert "(deleted)" not in result

    @pytest.mark.asyncio
    async def test_max_three_changes_shown(self):
        """Test that only first 3 changes are shown with overflow note."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I0001"})

        changes = [
            {"obj_class": "Person", "obj_handle": f"handle{i}"} for i in range(5)
        ]
        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Batch",
                "connection": {"user": {"name": "test"}},
                "changes": changes,
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "... and 2 more" in result
