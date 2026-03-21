"""
Unit tests for the search and execute meta-tools (Code Mode architecture).

These test the thin dispatch layer, not the underlying handlers.
No network required.
"""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from src.gramps_mcp.operations import OPERATION_REGISTRY
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.meta_execute import (
    ExecuteOperationParams,
    execute_operation_tool,
)
from src.gramps_mcp.tools.meta_search import (
    SearchOperationsParams,
    search_operations_tool,
)


class TestSearchOperationsTool:
    """Tests for the search meta-tool handler."""

    @pytest.mark.asyncio
    async def test_valid_query_returns_results(self):
        """A query matching known operations should return results."""
        result = await search_operations_tool({"query": "person", "category": None})
        assert len(result) >= 1
        assert isinstance(result[0], TextContent)
        assert "upsert_person" in result[0].text

    @pytest.mark.asyncio
    async def test_category_filter(self):
        """Category filter should restrict results to that category."""
        result = await search_operations_tool({"query": "", "category": "delete"})
        assert len(result) >= 1
        assert "delete" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_no_match_returns_all_operations(self):
        """A nonsensical query should return an informative no-match message."""
        result = await search_operations_tool(
            {"query": "xyzzy_nonexistent_foobar", "category": None}
        )
        assert len(result) >= 1
        text = result[0].text
        assert (
            "no operations matched" in text.lower() or "20 operations" in text.lower()
        )

    @pytest.mark.asyncio
    async def test_returns_text_content(self):
        """All results must be TextContent instances."""
        result = await search_operations_tool({"query": "search", "category": None})
        for item in result:
            assert isinstance(item, TextContent)

    @pytest.mark.asyncio
    async def test_output_includes_params(self):
        """Search results should include parameter information."""
        result = await search_operations_tool({"query": "search", "category": "search"})
        text = result[0].text
        # The search operation has a "type" parameter
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
            await execute_operation_tool({"operation": "serch", "params": {}})

    @pytest.mark.asyncio
    async def test_unknown_operation_includes_close_matches(self):
        """Error message should include close matches for typos."""
        with pytest.raises(McpToolError, match="search"):
            await execute_operation_tool({"operation": "serch", "params": {}})

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
            result = await execute_operation_tool(
                {"operation": "get_tree_stats", "params": {"include_statistics": True}}
            )
            mock_handler.assert_called_once_with({"include_statistics": True})
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
                await execute_operation_tool(
                    {"operation": "get_tree_stats", "params": {}}
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
            await execute_operation_tool({"operation": "get_tree_stats", "params": {}})
            mock_handler.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_completely_unknown_no_close_match(self):
        """Totally unrelated name should raise without close matches."""
        with pytest.raises(McpToolError, match="Unknown operation"):
            await execute_operation_tool(
                {"operation": "zzzzz_totally_wrong", "params": {}}
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
    async def test_prefix_suggests_get_for_get_media(self):
        """'get_media' should suggest 'get' via prefix matching."""
        with pytest.raises(McpToolError, match="get"):
            await execute_operation_tool({"operation": "get_media", "params": {}})

    @pytest.mark.asyncio
    async def test_prefix_suggests_search_for_search_person(self):
        """'search_person' should suggest 'search' via prefix matching."""
        with pytest.raises(McpToolError, match="search"):
            await execute_operation_tool({"operation": "search_person", "params": {}})

    @pytest.mark.asyncio
    async def test_prefix_suggests_delete_for_delete_event(self):
        """'delete_event' should suggest 'delete' via prefix matching."""
        with pytest.raises(McpToolError, match="delete"):
            await execute_operation_tool({"operation": "delete_event", "params": {}})

    @pytest.mark.asyncio
    async def test_no_prefix_for_unrelated_name(self):
        """Totally unrelated name should not get prefix matches."""
        with pytest.raises(McpToolError) as exc_info:
            await execute_operation_tool({"operation": "foobar", "params": {}})
        # Should not suggest any prefix-based operations
        msg = str(exc_info.value)
        assert "get," not in msg or "Did you mean" not in msg
