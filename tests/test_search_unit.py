"""
Unit tests for search_basic.py and search_details.py pure logic.

Tests format_search_result_by_type, _search_entities, search_tool,
search_text_tool, list_tags_tool, and get_tool dispatch without
network calls.
"""

from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from src.gramps_mcp.tools._errors import McpToolError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_settings():
    """Return a mock settings object with a tree ID."""
    settings = type("Settings", (), {"gramps_tree_id": "tree1"})()
    return settings


def _mock_client(handler_return="• **Mocked** result\n\n"):
    """Return a mock client whose make_api_call returns a configurable value."""
    client = AsyncMock()
    client.make_api_call = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


# ============================================================================
# format_search_result_by_type
# ============================================================================


class TestFormatSearchResultByType:
    """Test entity-type dispatch in format_search_result_by_type."""

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_no_handle(self, _mock):
        """Items without a handle get a generic line."""
        from src.gramps_mcp.tools.search_basic import format_search_result_by_type

        item = {"object_type": "person", "object": {}}
        result = await format_search_result_by_type(AsyncMock(), item)
        assert "Person record" in result
        assert "No handle" in result

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_person_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• person\n")
        with patch.dict(FORMATTER_DISPATCH, {"person": mock_handler}):
            item = {"object_type": "person", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• person\n"
        mock_handler.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_family_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• family\n")
        with patch.dict(FORMATTER_DISPATCH, {"family": mock_handler}):
            item = {"object_type": "family", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• family\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_event_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• event\n")
        with patch.dict(FORMATTER_DISPATCH, {"event": mock_handler}):
            item = {"object_type": "event", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• event\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_place_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• place\n")
        with patch.dict(FORMATTER_DISPATCH, {"place": mock_handler}):
            item = {"object_type": "place", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• place\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_source_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• source\n")
        with patch.dict(FORMATTER_DISPATCH, {"source": mock_handler}):
            item = {"object_type": "source", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• source\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_media_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• media\n")
        with patch.dict(FORMATTER_DISPATCH, {"media": mock_handler}):
            item = {"object_type": "media", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• media\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_citation_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• cite\n")
        with patch.dict(FORMATTER_DISPATCH, {"citation": mock_handler}):
            item = {"object_type": "citation", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• cite\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_note_type(self, _mock):
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value="• note\n")
        with patch.dict(FORMATTER_DISPATCH, {"note": mock_handler}):
            item = {"object_type": "note", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == "• note\n"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_unknown_type(self, _mock):
        """Unknown types produce a generic line with gramps_id."""
        from src.gramps_mcp.tools.search_basic import format_search_result_by_type

        item = {
            "object_type": "widget",
            "object": {"handle": "h1", "gramps_id": "W99", "title": "Widget One"},
        }
        result = await format_search_result_by_type(AsyncMock(), item)
        assert "Widget One" in result
        assert "W99" in result

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_unknown_type_no_title(self, _mock):
        """Unknown type with no title or desc falls back to type name."""
        from src.gramps_mcp.tools.search_basic import format_search_result_by_type

        item = {"object_type": "widget", "object": {"handle": "h1"}}
        result = await format_search_result_by_type(AsyncMock(), item)
        assert "Widget record" in result

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_handler_exception(self, _mock):
        """Exception in handler produces a graceful fallback line."""
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.dict(FORMATTER_DISPATCH, {"person": mock_handler}):
            item = {
                "object_type": "person",
                "object": {"handle": "h1", "gramps_id": "I99"},
            }
            result = await format_search_result_by_type(AsyncMock(), item)
        assert "Error formatting" in result
        assert "I99" in result

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_event_returns_none(self, _mock):
        """Event handler returning None should produce empty string."""
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value=None)
        with patch.dict(FORMATTER_DISPATCH, {"event": mock_handler}):
            item = {"object_type": "event", "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == ""


# ============================================================================
# _search_entities
# ============================================================================


class TestSearchEntities:
    """Test _search_entities response parsing and formatting."""

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_empty_list_response(self, _mock):
        """Empty list response says 'No X found'."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=[])
        handler = AsyncMock(return_value="• result\n")

        result = await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert "No people found" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_list_response_with_results(self, _mock):
        """List response formats each item with the handler."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        items = [{"handle": "h1"}, {"handle": "h2"}]
        client.make_api_call = AsyncMock(return_value=items)
        handler = AsyncMock(return_value="• item\n")

        result = await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert "Found 2 people" in result[0].text
        assert handler.await_count == 2

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_dict_response(self, _mock):
        """Dict response with 'data' key and total_count."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(
            return_value={
                "data": [{"handle": "h1"}],
                "total_count": 50,
            }
        )
        handler = AsyncMock(return_value="• item\n")

        result = await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert "Found 50 people" in result[0].text
        assert "showing 1" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_skips_non_dict_items(self, _mock):
        """Non-dict items in results are skipped."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=["not_a_dict", {"handle": "h1"}])
        handler = AsyncMock(return_value="• item\n")

        await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert handler.await_count == 1

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_item_without_handle_skipped(self, _mock):
        """Items with empty handle are skipped."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=[{"gramps_id": "I1"}])
        handler = AsyncMock(return_value="• item\n")

        await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert handler.await_count == 0

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_wrapped_object_item(self, _mock):
        """Items wrapped in {'object': {...}} are unwrapped."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(
            return_value=[{"object": {"handle": "h1"}, "object_type": "person"}]
        )
        handler = AsyncMock(return_value="• item\n")

        await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert handler.await_count == 1

    @pytest.mark.asyncio
    async def test_validation_error_raises(self):
        """Invalid parameters raise McpToolError."""
        from src.gramps_mcp.models.parameters.source_params import SourceSearchParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        with pytest.raises(McpToolError, match="search"):
            await _search_entities(
                client,
                {"sort": "invalid_sort_key"},
                SourceSearchParams,
                "GET_SOURCES",
                "sources",
                AsyncMock(),
            )


# ============================================================================
# list_tags_tool
# ============================================================================


class TestFindTagsTool:
    """Test list_tags_tool formatting."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_empty_tags(self, _settings, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import list_tags_tool

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value=[])
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await list_tags_tool({})
        assert "No tags found" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_tags_list(self, _settings, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import list_tags_tool

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value=[
                {"name": "ToDo", "handle": "tag1", "color": "#FF0000", "priority": 1},
                {"name": "Done", "handle": "tag2", "color": "#00FF00", "priority": 0},
            ]
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await list_tags_tool({})
        text = result[0].text
        assert "Found 2 tags" in text
        assert "ToDo" in text
        assert "Done" in text
        assert "#FF0000" in text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_tags_dict_response(self, _settings, mock_client_cls):
        """Dict response with 'data' key works correctly."""
        from src.gramps_mcp.tools.search_basic import list_tags_tool

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={
                "data": [
                    {
                        "name": "Review",
                        "handle": "tag3",
                        "color": "#0000FF",
                        "priority": 2,
                    }
                ]
            }
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await list_tags_tool({})
        text = result[0].text
        assert "Found 1 tags" in text
        assert "Review" in text


# ============================================================================
# search_tool
# ============================================================================


class TestFindTypeTool:
    """Test search_tool dispatch logic."""

    @pytest.mark.asyncio
    async def test_missing_entity_type(self):
        """Missing type returns error message (not exception)."""
        from src.gramps_mcp.tools.search_basic import search_tool

        result = await search_tool({"gql": "test"})
        assert "Entity type is required" in result[0].text

    @pytest.mark.asyncio
    async def test_unsupported_entity_type(self):
        """Unknown entity type returns not-supported message."""
        from src.gramps_mcp.tools.search_basic import search_tool

        result = await search_tool({"type": "unicorn", "gql": "test"})
        assert "not supported" in result[0].text

    @pytest.mark.asyncio
    async def test_enum_entity_type(self):
        """Enum-like types with .value are handled."""
        from src.gramps_mcp.tools.search_basic import search_tool

        class FakeEnum:
            value = "nonexistent"

        result = await search_tool({"type": FakeEnum(), "gql": "test"})
        assert "not supported" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_person_dispatch(self, _settings, mock_client_cls):
        """type=person dispatches to search_person_tool."""
        from src.gramps_mcp.tools.search_basic import search_tool

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value=[])
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await search_tool({"type": "person", "gql": "test", "max_results": 1})
        assert isinstance(result[0], TextContent)


# ============================================================================
# search_text_tool
# ============================================================================


class TestFindAnythingTool:
    """Test search_text_tool response formatting."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_empty_results(self, _settings, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value=([], {"x-total-count": "0"}))
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert "No records found" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.format_search_result_by_type",
        new_callable=AsyncMock,
        return_value="• item\n",
    )
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_list_response(self, _settings, mock_client_cls, mock_fmt):
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = AsyncMock()
        items = [{"object_type": "person", "object": {"handle": "h1"}}]
        client_inst.make_api_call = AsyncMock(
            return_value=(items, {"x-total-count": "1"})
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert "Found 1 records" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.format_search_result_by_type",
        new_callable=AsyncMock,
        return_value="• item\n",
    )
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_truncated_display(self, _settings, mock_client_cls, mock_fmt):
        """When total_count > displayed_count, show 'showing N'."""
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = AsyncMock()
        items = [{"object_type": "person", "object": {"handle": "h1"}}]
        client_inst.make_api_call = AsyncMock(
            return_value=(items, {"x-total-count": "100"})
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        text = result[0].text
        assert "Found 100 records" in text
        assert "showing 1" in text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.format_search_result_by_type",
        new_callable=AsyncMock,
        return_value="• item\n",
    )
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_dict_response(self, _settings, mock_client_cls, mock_fmt):
        """Dict response with 'data' key parsed correctly."""
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = AsyncMock()
        resp_dict = {"data": [{"object_type": "event", "object": {"handle": "h1"}}]}
        client_inst.make_api_call = AsyncMock(
            return_value=(resp_dict, {"x-total-count": "1"})
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert "Found 1 records" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.search_basic.get_settings", return_value=_mock_settings()
    )
    async def test_skips_non_dict_items(self, _settings, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = AsyncMock()
        items = ["not_a_dict", {"object_type": "person", "object": {"handle": "h1"}}]
        client_inst.make_api_call = AsyncMock(
            return_value=(items, {"x-total-count": "2"})
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert isinstance(result[0], TextContent)


# ============================================================================
# get_tool (search_details.py)
# ============================================================================


class TestGetTypeTool:
    """Test get_tool dispatch and gramps_id resolution."""

    @pytest.mark.asyncio
    async def test_unsupported_type(self):
        """Unsupported entity type returns error message."""
        from src.gramps_mcp.tools.search_details import get_tool

        result = await get_tool({"type": "unicorn", "handle": "h1"})
        assert "not supported" in result[0].text

    @pytest.mark.asyncio
    async def test_no_handle_no_gramps_id(self):
        """Neither handle nor gramps_id returns resolution error."""
        from src.gramps_mcp.tools.search_details import get_tool

        result = await get_tool({"type": "event"})
        assert "Could not resolve" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_details.get_person_tool", new_callable=AsyncMock
    )
    async def test_person_dispatch(self, mock_tool):
        """type=person dispatches to get_person_tool."""
        from src.gramps_mcp.tools.search_details import get_tool

        mock_tool.return_value = [TextContent(type="text", text="person details")]
        result = await get_tool({"type": "person", "handle": "h1"})
        mock_tool.assert_awaited_once_with({"person_handle": "h1"})
        assert result[0].text == "person details"

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_details.get_family_tool", new_callable=AsyncMock
    )
    async def test_family_dispatch(self, mock_tool):
        """type=family dispatches to get_family_tool."""
        from src.gramps_mcp.tools.search_details import get_tool

        mock_tool.return_value = [TextContent(type="text", text="family details")]
        result = await get_tool({"type": "family", "handle": "h1"})
        mock_tool.assert_awaited_once_with({"family_handle": "h1"})
        assert result[0].text == "family details"

    @pytest.mark.asyncio
    async def test_event_dispatch(self):
        """type=event dispatches via _GET_TOOL_DISPATCH."""
        from src.gramps_mcp.tools import search_details

        mock_tool = AsyncMock(
            return_value=[TextContent(type="text", text="event details")]
        )
        original = search_details._GET_TOOL_DISPATCH["event"]
        search_details._GET_TOOL_DISPATCH["event"] = mock_tool
        try:
            await search_details.get_tool({"type": "event", "handle": "h1"})
            mock_tool.assert_awaited_once_with({"handle": "h1"})
        finally:
            search_details._GET_TOOL_DISPATCH["event"] = original

    @pytest.mark.asyncio
    async def test_note_dispatch(self):
        """type=note dispatches via _GET_TOOL_DISPATCH."""
        from src.gramps_mcp.tools import search_details

        mock_tool = AsyncMock(
            return_value=[TextContent(type="text", text="note details")]
        )
        original = search_details._GET_TOOL_DISPATCH["note"]
        search_details._GET_TOOL_DISPATCH["note"] = mock_tool
        try:
            await search_details.get_tool({"type": "note", "handle": "h1"})
            mock_tool.assert_awaited_once_with({"handle": "h1"})
        finally:
            search_details._GET_TOOL_DISPATCH["note"] = original

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.search_tool", new_callable=AsyncMock)
    async def test_gramps_id_resolution(self, mock_find):
        """gramps_id without handle triggers search then dispatch."""
        from src.gramps_mcp.tools import search_details

        mock_find.return_value = [
            TextContent(type="text", text="• Event [resolved_handle] - E0001")
        ]
        mock_get = AsyncMock(
            return_value=[TextContent(type="text", text="event details")]
        )
        original = search_details._GET_TOOL_DISPATCH["event"]
        search_details._GET_TOOL_DISPATCH["event"] = mock_get
        try:
            await search_details.get_tool({"type": "event", "gramps_id": "E0001"})
            mock_find.assert_awaited_once()
            mock_get.assert_awaited_once_with({"handle": "resolved_handle"})
        finally:
            search_details._GET_TOOL_DISPATCH["event"] = original

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.search_basic.search_tool", new_callable=AsyncMock)
    async def test_gramps_id_not_resolved(self, mock_find):
        """gramps_id that can't be resolved returns error."""
        from src.gramps_mcp.tools.search_details import get_tool

        mock_find.return_value = [TextContent(type="text", text="No events found")]
        result = await get_tool({"type": "event", "gramps_id": "E9999"})
        assert "Could not resolve" in result[0].text


# ============================================================================
# Individual get_*_tool missing-handle branches
# ============================================================================


class TestGetToolsMissingHandle:
    """Test that get_*_tool functions raise on missing handle."""

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_event_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_event_tool

        with pytest.raises(McpToolError, match="event details"):
            await get_event_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_place_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_place_tool

        with pytest.raises(McpToolError, match="place details"):
            await get_place_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_source_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_source_tool

        with pytest.raises(McpToolError, match="source details"):
            await get_source_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_citation_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_citation_tool

        with pytest.raises(McpToolError, match="citation details"):
            await get_citation_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_note_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_note_tool

        with pytest.raises(McpToolError, match="note details"):
            await get_note_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_media_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_media_tool

        with pytest.raises(McpToolError, match="media details"):
            await get_media_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_repository_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_repository_tool

        with pytest.raises(McpToolError, match="repository details"):
            await get_repository_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_person_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_person_tool

        with pytest.raises(McpToolError, match="person details"):
            await get_person_tool({})

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_get_family_no_handle(self, _):
        from src.gramps_mcp.tools.search_details import get_family_tool

        with pytest.raises(McpToolError, match="family details"):
            await get_family_tool({})
