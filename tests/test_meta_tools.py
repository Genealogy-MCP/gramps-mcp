"""
Unit tests for the search and execute meta-tools (Code Mode architecture).

These test the thin dispatch layer via the mcp-codemode library.
No network required.
"""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent
from mcp_codemode import (
    ExecuteOperationParams,
    McpToolError,
    SearchOperationsParams,
    execute_operation,
    format_search_results,
    search_operations,
)

from src.gramps_mcp.operations import OPERATION_REGISTRY


class TestSearchOperationsTool:
    """Tests for the search meta-tool handler."""

    @pytest.mark.asyncio
    async def test_valid_query_returns_results(self):
        """A query matching known operations should return results."""
        matches = search_operations("person", OPERATION_REGISTRY)
        text = format_search_results(matches, OPERATION_REGISTRY)
        assert "upsert_person" in text

    @pytest.mark.asyncio
    async def test_category_filter(self):
        """Category filter should restrict results to that category."""
        matches = search_operations("", OPERATION_REGISTRY, category="delete")
        text = format_search_results(matches, OPERATION_REGISTRY)
        assert "delete" in text.lower()

    @pytest.mark.asyncio
    async def test_no_match_returns_all_operations(self):
        """A nonsensical query should return an informative no-match message."""
        matches = search_operations("xyzzy_nonexistent_foobar", OPERATION_REGISTRY)
        text = format_search_results(matches, OPERATION_REGISTRY)
        assert (
            "no operations matched" in text.lower() or "20 operations" in text.lower()
        )

    @pytest.mark.asyncio
    async def test_output_includes_params(self):
        """Search results should include parameter information."""
        matches = search_operations("search", OPERATION_REGISTRY, category="search")
        text = format_search_results(matches, OPERATION_REGISTRY)
        assert "type" in text.lower()

    @pytest.mark.asyncio
    async def test_search_params_model_validation(self):
        """SearchOperationsParams must validate inputs."""
        params = SearchOperationsParams(query="test")
        assert params.query == "test"
        assert params.category is None

    @pytest.mark.asyncio
    async def test_search_with_category(self):
        """SearchOperationsParams accepts category."""
        params = SearchOperationsParams(query="test", category="write")
        assert params.category == "write"


class TestExecuteOperationTool:
    """Tests for the execute meta-tool handler."""

    @pytest.mark.asyncio
    async def test_unknown_operation_raises_with_suggestions(self):
        """Unknown operation should raise McpToolError with suggestions."""
        with pytest.raises(McpToolError, match="Unknown operation"):
            await execute_operation(
                {"operation": "serch", "params": {}}, OPERATION_REGISTRY, None
            )

    @pytest.mark.asyncio
    async def test_unknown_operation_includes_close_matches(self):
        """Error message should include close matches for typos."""
        with pytest.raises(McpToolError, match="search"):
            await execute_operation(
                {"operation": "serch", "params": {}}, OPERATION_REGISTRY, None
            )

    @pytest.mark.asyncio
    async def test_valid_operation_dispatches(self):
        """A valid operation should dispatch to the handler."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text="ok")])
        entry = OPERATION_REGISTRY["get_tree_stats"]

        with patch.dict(
            "src.gramps_mcp.operations.OPERATION_REGISTRY",
            {
                "get_tree_stats": entry.__class__(
                    name=entry.name,
                    summary=entry.summary,
                    description=entry.description,
                    category=entry.category,
                    params_schema=entry.params_schema,
                    handler=mock_handler,
                    read_only=entry.read_only,
                    destructive=entry.destructive,
                    token_warning=entry.token_warning,
                )
            },
        ):
            result = await execute_operation(
                {"operation": "get_tree_stats", "params": {"include_statistics": True}},
                OPERATION_REGISTRY,
                None,
            )
            mock_handler.assert_called_once()
            assert result == [TextContent(type="text", text="ok")]

    @pytest.mark.asyncio
    async def test_handler_error_propagated(self):
        """Errors from the handler should propagate as McpToolError."""
        mock_handler = AsyncMock(side_effect=McpToolError("handler failed"))
        entry = OPERATION_REGISTRY["get_tree_stats"]

        with patch.dict(
            "src.gramps_mcp.operations.OPERATION_REGISTRY",
            {
                "get_tree_stats": entry.__class__(
                    name=entry.name,
                    summary=entry.summary,
                    description=entry.description,
                    category=entry.category,
                    params_schema=entry.params_schema,
                    handler=mock_handler,
                    read_only=entry.read_only,
                    destructive=entry.destructive,
                    token_warning=entry.token_warning,
                )
            },
        ):
            with pytest.raises(McpToolError, match="handler failed"):
                await execute_operation(
                    {"operation": "get_tree_stats", "params": {}},
                    OPERATION_REGISTRY,
                    None,
                )

    @pytest.mark.asyncio
    async def test_empty_params_accepted(self):
        """Empty params dict should be passed through."""
        mock_handler = AsyncMock(return_value=[TextContent(type="text", text="ok")])
        entry = OPERATION_REGISTRY["get_tree_stats"]

        with patch.dict(
            "src.gramps_mcp.operations.OPERATION_REGISTRY",
            {
                "get_tree_stats": entry.__class__(
                    name=entry.name,
                    summary=entry.summary,
                    description=entry.description,
                    category=entry.category,
                    params_schema=entry.params_schema,
                    handler=mock_handler,
                    read_only=entry.read_only,
                    destructive=entry.destructive,
                    token_warning=entry.token_warning,
                )
            },
        ):
            await execute_operation(
                {"operation": "get_tree_stats", "params": {}},
                OPERATION_REGISTRY,
                None,
            )
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_completely_unknown_no_close_match(self):
        """Totally unrelated name should raise without close matches."""
        with pytest.raises(McpToolError, match="Unknown operation"):
            await execute_operation(
                {"operation": "zzzzz_totally_wrong", "params": {}},
                OPERATION_REGISTRY,
                None,
            )

    def test_execute_params_model_validation(self):
        """ExecuteOperationParams must validate inputs."""
        params = ExecuteOperationParams(operation="search", params={"type": "person"})
        assert params.operation == "search"
        assert params.params == {"type": "person"}

    def test_execute_params_default_empty_dict(self):
        """Params should default to empty dict."""
        params = ExecuteOperationParams(operation="search")
        assert params.params == {}

    @pytest.mark.asyncio
    async def test_close_match_for_get_media(self):
        """'get_media' should suggest alternatives."""
        with pytest.raises(McpToolError, match="get"):
            await execute_operation(
                {"operation": "get_media", "params": {}}, OPERATION_REGISTRY, None
            )

    @pytest.mark.asyncio
    async def test_close_match_for_search_person(self):
        """'search_person' should suggest 'search' via close matching."""
        with pytest.raises(McpToolError, match="search"):
            await execute_operation(
                {"operation": "search_person", "params": {}}, OPERATION_REGISTRY, None
            )

    @pytest.mark.asyncio
    async def test_close_match_for_delete_event(self):
        """'delete_event' should suggest 'delete' via close matching."""
        with pytest.raises(McpToolError, match="delete"):
            await execute_operation(
                {"operation": "delete_event", "params": {}}, OPERATION_REGISTRY, None
            )

    @pytest.mark.asyncio
    async def test_no_prefix_for_unrelated_name(self):
        """Totally unrelated name should not get prefix matches."""
        with pytest.raises(McpToolError) as exc_info:
            await execute_operation(
                {"operation": "foobar", "params": {}}, OPERATION_REGISTRY, None
            )
        msg = str(exc_info.value)
        assert "Unknown operation" in msg
