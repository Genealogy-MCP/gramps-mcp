"""
Unit tests for tools/analysis.py — formatting functions, task polling,
tree stats, report tools, and report download retry logic.

Tests mock GrampsWebAPIClient to avoid network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.analysis import (
    _fetch_report_with_retry,
    _format_recent_changes,
    _format_tree_info,
    _wait_for_task_completion,
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
)


def _mock_settings(tree_id: str = "tree1"):
    return type("Settings", (), {"gramps_tree_id": tree_id})()


# ---------------------------------------------------------------------------
# _format_recent_changes (async, uses get_gramps_id_from_handle)
# ---------------------------------------------------------------------------


class TestFormatRecentChanges:
    """Test _format_recent_changes formatting branches."""

    @pytest.mark.asyncio
    async def test_empty_transactions(self):
        result = await _format_recent_changes([], AsyncMock(), "t1")
        assert result == "No recent changes found."

    @pytest.mark.asyncio
    async def test_string_timestamp(self):
        """String timestamps are used as-is."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I001"})

        transactions = [
            {
                "timestamp": "2024-01-15 10:30:00",
                "description": "Edit",
                "connection": {"user": {"name": "admin"}},
                "changes": [{"obj_class": "Person", "obj_handle": "h1"}],
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "2024-01-15 10:30:00" in result
        assert "I001" in result

    @pytest.mark.asyncio
    async def test_int_timestamp_converted(self):
        """Integer timestamps are converted to datetime."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "E001"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Add event",
                "connection": {"user": {"name": "tester"}},
                "changes": [{"obj_class": "Event", "obj_handle": "e1"}],
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "tester" in result
        assert "E001" in result

    @pytest.mark.asyncio
    async def test_missing_connection_user(self):
        """Missing connection/user shows 'Unknown'."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I001"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Test",
                "changes": [{"obj_class": "Person", "obj_handle": "h1"}],
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "Unknown" in result

    @pytest.mark.asyncio
    async def test_missing_user_in_connection(self):
        """Connection with no user shows 'Unknown'."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I001"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Test",
                "connection": {},
                "changes": [{"obj_class": "Person", "obj_handle": "h1"}],
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "Unknown" in result

    @pytest.mark.asyncio
    async def test_empty_changes_list(self):
        """Empty changes list shows '0 objects modified'."""
        client = AsyncMock()

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Empty batch",
                "connection": {"user": {"name": "admin"}},
                "changes": [],
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "0 objects modified" in result

    @pytest.mark.asyncio
    async def test_hex_handle_shows_deleted(self):
        """Hex-like gramps_id (deleted object) shows '(deleted)'."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("404"))

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Delete",
                "connection": {"user": {"name": "admin"}},
                "changes": [{"obj_class": "Person", "obj_handle": "abcdef1234567890"}],
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "(deleted)" in result

    @pytest.mark.asyncio
    async def test_more_than_3_changes(self):
        """More than 3 changes shows overflow note."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I001"})

        changes = [{"obj_class": "Person", "obj_handle": f"h{i}"} for i in range(5)]
        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Batch",
                "connection": {"user": {"name": "admin"}},
                "changes": changes,
            }
        ]

        result = await _format_recent_changes(transactions, client, "t1")
        assert "... and 2 more" in result


# ---------------------------------------------------------------------------
# _wait_for_task_completion
# ---------------------------------------------------------------------------


class TestWaitForTaskCompletion:
    """Test _wait_for_task_completion polling logic."""

    @pytest.mark.asyncio
    async def test_immediate_success_with_result_object(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        client._make_request = AsyncMock(
            return_value={
                "state": "SUCCESS",
                "result_object": {"file_name": "report.html"},
            }
        )

        result = await _wait_for_task_completion(client, "task1", "t1")
        assert result == {"file_name": "report.html"}

    @pytest.mark.asyncio
    async def test_success_with_result_fallback(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        client._make_request = AsyncMock(
            return_value={
                "state": "SUCCESS",
                "result": {"file_name": "out.html"},
            }
        )

        result = await _wait_for_task_completion(client, "task2", "t1")
        assert result == {"file_name": "out.html"}

    @pytest.mark.asyncio
    async def test_success_no_result_returns_task_status(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        task_status = {"state": "SUCCESS"}
        client._make_request = AsyncMock(return_value=task_status)

        result = await _wait_for_task_completion(client, "task3", "t1")
        assert result == task_status

    @pytest.mark.asyncio
    async def test_failure_raises(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        client._make_request = AsyncMock(
            return_value={"state": "FAILURE", "info": "Out of memory"}
        )

        with pytest.raises(GrampsAPIError, match="failed"):
            await _wait_for_task_completion(client, "task4", "t1")

    @pytest.mark.asyncio
    async def test_failed_state_raises(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        client._make_request = AsyncMock(
            return_value={"state": "FAILED", "info": "error"}
        )

        with pytest.raises(GrampsAPIError, match="failed"):
            await _wait_for_task_completion(client, "task5", "t1")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        client._make_request = AsyncMock(return_value={"state": "PENDING"})

        with pytest.raises(GrampsAPIError, match="timed out"):
            await _wait_for_task_completion(client, "task6", "t1", timeout=0)

    @pytest.mark.asyncio
    async def test_polling_error_raises(self):
        client = MagicMock()
        client.base_url = "http://test/api"
        client._make_request = AsyncMock(side_effect=RuntimeError("network error"))

        with pytest.raises(GrampsAPIError, match="Error polling"):
            await _wait_for_task_completion(client, "task7", "t1")


# ---------------------------------------------------------------------------
# _format_tree_info  (pure function)
# ---------------------------------------------------------------------------


class TestFormatTreeInfo:
    """Test _format_tree_info output."""

    def test_full_tree_info(self):
        tree = {
            "id": "tree1",
            "name": "Smith Family",
            "description": "Three generations",
            "usage_people": 2157,
        }
        result = _format_tree_info(tree)
        assert "Smith Family" in result
        assert "tree1" in result
        assert "Three generations" in result
        assert "2,157" in result

    def test_no_description(self):
        tree = {
            "id": "t2",
            "name": "Jones",
            "usage_people": 100,
        }
        result = _format_tree_info(tree)
        assert "Jones" in result
        assert "Description" not in result

    def test_no_usage_stats(self):
        tree = {"id": "t3", "name": "Empty"}
        result = _format_tree_info(tree)
        assert "Statistics not available" in result

    def test_no_stats_available(self):
        tree = {"id": "t4", "name": "No Stats"}
        result = _format_tree_info(tree)
        assert "Statistics not available" in result


# ---------------------------------------------------------------------------
# get_tree_stats_tool
# ---------------------------------------------------------------------------


class TestGetTreeStatsTool:
    """Test get_tree_stats_tool dispatch.

    The @with_client decorator injects a GrampsWebAPIClient as the first arg,
    so we patch GrampsWebAPIClient at the search_basic module level (where
    with_client imports it) and call the tool with just the arguments dict.
    """

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_with_tree_id(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"id": "tree1", "name": "My Tree", "usage_people": 50}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_tree_stats_tool({})
        assert "My Tree" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings(""),
    )
    async def test_auto_discover_tree(self, _settings, mock_client_cls):
        """Empty tree_id triggers auto-discovery from /trees/."""
        client_inst = AsyncMock()

        async def mock_api_call(api_call, params=None, tree_id=None, **kw):
            if api_call.name == "GET_TREES":
                return [{"id": "discovered_tree"}]
            return {
                "id": "discovered_tree",
                "name": "Found",
                "usage_people": 10,
            }

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_tree_stats_tool({})
        assert "Found" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings(""),
    )
    async def test_no_trees_found_error(self, _settings, mock_client_cls):
        """No trees found raises McpToolError."""
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value=[])
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError, match="No trees found"):
            await get_tree_stats_tool({})


# ---------------------------------------------------------------------------
# get_recent_changes_tool
# ---------------------------------------------------------------------------


class TestGetRecentChangesTool:
    """Test get_recent_changes_tool dispatch."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_recent_changes_happy_path(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value=[
                {
                    "timestamp": "2024-01-01 10:00:00",
                    "description": "Edit",
                    "connection": {"user": {"name": "admin"}},
                    "changes": [{"obj_class": "Person", "obj_handle": "h1"}],
                }
            ]
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_recent_changes_tool({})
        assert len(result) == 1
        assert "admin" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_recent_changes_empty(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value=[])
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_recent_changes_tool({})
        assert "No recent changes" in result[0].text


# ---------------------------------------------------------------------------
# get_descendants_tool
# ---------------------------------------------------------------------------


class TestGetDescendantsTool:
    """Test get_descendants_tool report flow."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_sync_response_with_filename(self, _settings, mock_client_cls):
        """Direct sync response with file_name."""
        client_inst = AsyncMock()
        call_count = {"count": 0}

        async def mock_api_call(api_call, params=None, tree_id=None, **kw):
            call_count["count"] += 1
            name = api_call.name
            if name == "POST_REPORT_FILE":
                return {"file_name": "report.html"}
            if name == "GET_REPORT_PROCESSED":
                return {"raw_content": "<h1>Descendants</h1>"}
            return {}

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_descendants_tool({"gramps_id": "I0001"})
        assert "Descendants" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_async_task_response(self, _settings, mock_client_cls):
        """Async task response that requires polling."""
        client_inst = MagicMock()
        client_inst.base_url = "http://test/api"

        async def mock_api_call(api_call, params=None, tree_id=None, **kw):
            name = api_call.name
            if name == "POST_REPORT_FILE":
                return {"task": {"id": "task123"}}
            if name == "GET_REPORT_PROCESSED":
                return {"raw_content": "<h1>Report</h1>"}
            return {}

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst._make_request = AsyncMock(
            return_value={
                "state": "SUCCESS",
                "result_object": {"file_name": "output.html"},
            }
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_descendants_tool({"gramps_id": "I0001"})
        assert "Report" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_missing_gramps_id_raises(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await get_descendants_tool({})

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_no_filename_no_task_raises(self, _settings, mock_client_cls):
        """Report response without filename or task raises error."""
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value={})
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await get_descendants_tool({"gramps_id": "I0001"})

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_with_max_generations(self, _settings, mock_client_cls):
        """Custom max_generations passed to report options."""
        client_inst = AsyncMock()

        async def mock_api_call(api_call, params=None, tree_id=None, **kw):
            name = api_call.name
            if name == "POST_REPORT_FILE":
                return {"file_name": "report.html"}
            if name == "GET_REPORT_PROCESSED":
                return "plain text report"
            return {}

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_descendants_tool(
            {"gramps_id": "I0001", "max_generations": 3}
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# get_ancestors_tool
# ---------------------------------------------------------------------------


class TestGetAncestorsTool:
    """Test get_ancestors_tool report flow."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_sync_response(self, _settings, mock_client_cls):
        client_inst = AsyncMock()

        async def mock_api_call(api_call, params=None, tree_id=None, **kw):
            name = api_call.name
            if name == "POST_REPORT_FILE":
                return {"file_name": "ancestors.html"}
            if name == "GET_REPORT_PROCESSED":
                return {"raw_content": "<h1>Ancestors</h1>"}
            return {}

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_ancestors_tool({"gramps_id": "I0001"})
        assert "Ancestors" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_async_task_response(self, _settings, mock_client_cls):
        client_inst = MagicMock()
        client_inst.base_url = "http://test/api"

        async def mock_api_call(api_call, params=None, tree_id=None, **kw):
            name = api_call.name
            if name == "POST_REPORT_FILE":
                return {"task": {"id": "task456"}}
            if name == "GET_REPORT_PROCESSED":
                return {"raw_content": "<h1>Ancestor Report</h1>"}
            return {}

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst._make_request = AsyncMock(
            return_value={
                "state": "SUCCESS",
                "result_object": {"file_name": "output.html"},
            }
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await get_ancestors_tool({"gramps_id": "I0001"})
        assert "Ancestor Report" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_missing_gramps_id(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await get_ancestors_tool({})

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.analysis.get_settings",
        return_value=_mock_settings("tree1"),
    )
    async def test_no_filename_no_task(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value={})
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await get_ancestors_tool({"gramps_id": "I0001"})


# ---------------------------------------------------------------------------
# _fetch_report_with_retry
# ---------------------------------------------------------------------------


class TestFetchReportWithRetry:
    """Test retry logic for processed report file downloads.

    After a Celery task completes, the generated file may not be immediately
    available via the web endpoint. This helper retries on 404 with
    exponential backoff to handle the race condition.
    """

    @pytest.mark.asyncio
    async def test_immediate_success(self):
        """First call succeeds — no retry needed."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(
            return_value={"raw_content": "<h1>Report</h1>"}
        )

        result = await _fetch_report_with_retry(
            client, "tree1", "descend_report", "output.html"
        )
        assert result == "<h1>Report</h1>"
        assert client.make_api_call.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_404_then_success(self):
        """First call gets 404, second succeeds."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(
            side_effect=[
                GrampsAPIError("Record not found at /reports/descend_report/file"),
                {"raw_content": "<h1>Descendants</h1>"},
            ]
        )

        result = await _fetch_report_with_retry(
            client,
            "tree1",
            "descend_report",
            "output.html",
            initial_delay=0.01,
        )
        assert result == "<h1>Descendants</h1>"
        assert client.make_api_call.call_count == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        """All attempts return 404 — raises GrampsAPIError."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(
            side_effect=GrampsAPIError("Record not found at /reports/file")
        )

        with pytest.raises(GrampsAPIError, match="not found"):
            await _fetch_report_with_retry(
                client,
                "tree1",
                "descend_report",
                "output.html",
                max_retries=2,
                initial_delay=0.01,
            )
        # 1 initial + 2 retries = 3 calls
        assert client.make_api_call.call_count == 3

    @pytest.mark.asyncio
    async def test_non_404_error_not_retried(self):
        """Non-404 errors (e.g. 500) raise immediately without retry."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(
            side_effect=GrampsAPIError("Server error at /reports/file")
        )

        with pytest.raises(GrampsAPIError, match="Server error"):
            await _fetch_report_with_retry(
                client,
                "tree1",
                "descend_report",
                "output.html",
                initial_delay=0.01,
            )
        assert client.make_api_call.call_count == 1
