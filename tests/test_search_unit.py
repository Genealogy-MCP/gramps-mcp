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

_SETTINGS_PATCH = "src.gramps_mcp.tools.search_basic.get_settings"
_CLIENT_PATCH = "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient"


def _mock_settings():
    """Return a mock settings object with a tree ID."""
    return type("Settings", (), {"gramps_tree_id": "tree1"})()


def _mock_client_instance():
    """Return a pre-configured mock client for tool tests."""
    client = AsyncMock()
    client.make_api_call = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


# ============================================================================
# format_search_result_by_type
# ============================================================================

# Entity types that all follow the same dispatch pattern
_DISPATCH_ENTITY_TYPES = [
    "person",
    "family",
    "event",
    "place",
    "source",
    "media",
    "citation",
    "note",
]


class TestFormatSearchResultByType:
    """Test entity-type dispatch in format_search_result_by_type."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(_SETTINGS_PATCH, return_value=_mock_settings()):
            yield

    @pytest.mark.asyncio
    async def test_no_handle(self):
        """Items without a handle get a generic line."""
        from src.gramps_mcp.tools.search_basic import format_search_result_by_type

        item = {"object_type": "person", "object": {}}
        result = await format_search_result_by_type(AsyncMock(), item)
        assert "Person record" in result
        assert "No handle" in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("entity_type", _DISPATCH_ENTITY_TYPES)
    async def test_entity_type_dispatch(self, entity_type):
        """Each known entity type dispatches to its formatter."""
        from src.gramps_mcp.tools.search_basic import (
            FORMATTER_DISPATCH,
            format_search_result_by_type,
        )

        mock_handler = AsyncMock(return_value=f"* {entity_type}\n")
        with patch.dict(FORMATTER_DISPATCH, {entity_type: mock_handler}):
            item = {"object_type": entity_type, "object": {"handle": "h1"}}
            result = await format_search_result_by_type(AsyncMock(), item)
        assert result == f"* {entity_type}\n"
        mock_handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_type(self):
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
    async def test_unknown_type_no_title(self):
        """Unknown type with no title or desc falls back to type name."""
        from src.gramps_mcp.tools.search_basic import format_search_result_by_type

        item = {"object_type": "widget", "object": {"handle": "h1"}}
        result = await format_search_result_by_type(AsyncMock(), item)
        assert "Widget record" in result

    @pytest.mark.asyncio
    async def test_handler_exception(self):
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
    async def test_event_returns_none(self):
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

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(_SETTINGS_PATCH, return_value=_mock_settings()):
            yield

    @pytest.mark.asyncio
    async def test_empty_list_response(self):
        """Empty list response says 'No X found'."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=[])
        handler = AsyncMock(return_value="* result\n")

        result = await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert "No people found" in result[0].text

    @pytest.mark.asyncio
    async def test_list_response_with_results(self):
        """List response formats each item with the handler."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        items = [{"handle": "h1"}, {"handle": "h2"}]
        client.make_api_call = AsyncMock(return_value=items)
        handler = AsyncMock(return_value="* item\n")

        result = await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert "Found 2 people" in result[0].text
        assert handler.await_count == 2

    @pytest.mark.asyncio
    async def test_dict_response(self):
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
        handler = AsyncMock(return_value="* item\n")

        result = await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert "Found 50 people" in result[0].text
        assert "showing 1" in result[0].text

    @pytest.mark.asyncio
    async def test_skips_non_dict_items(self):
        """Non-dict items in results are skipped."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=["not_a_dict", {"handle": "h1"}])
        handler = AsyncMock(return_value="* item\n")

        await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert handler.await_count == 1

    @pytest.mark.asyncio
    async def test_item_without_handle_skipped(self):
        """Items with empty handle are skipped."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=[{"gramps_id": "I1"}])
        handler = AsyncMock(return_value="* item\n")

        await _search_entities(
            client, {}, BaseGetMultipleParams, "GET_PEOPLE", "people", handler
        )
        assert handler.await_count == 0

    @pytest.mark.asyncio
    async def test_wrapped_object_item(self):
        """Items wrapped in {'object': {...}} are unwrapped."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(
            return_value=[{"object": {"handle": "h1"}, "object_type": "person"}]
        )
        handler = AsyncMock(return_value="* item\n")

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

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(_SETTINGS_PATCH, return_value=_mock_settings()):
            yield

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    async def test_empty_tags(self, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import list_tags_tool

        client_inst = _mock_client_instance()
        mock_client_cls.return_value = client_inst

        result = await list_tags_tool({})
        assert "No tags found" in result[0].text

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    async def test_tags_list(self, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import list_tags_tool

        client_inst = _mock_client_instance()
        client_inst.make_api_call = AsyncMock(
            return_value=[
                {"name": "ToDo", "handle": "tag1", "color": "#FF0000", "priority": 1},
                {"name": "Done", "handle": "tag2", "color": "#00FF00", "priority": 0},
            ]
        )
        mock_client_cls.return_value = client_inst

        result = await list_tags_tool({})
        text = result[0].text
        assert "Found 2 tags" in text
        assert "ToDo" in text
        assert "Done" in text
        assert "#FF0000" in text

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    async def test_tags_dict_response(self, mock_client_cls):
        """Dict response with 'data' key works correctly."""
        from src.gramps_mcp.tools.search_basic import list_tags_tool

        client_inst = _mock_client_instance()
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
    async def test_missing_entity_type_raises(self):
        """Missing type raises McpToolError (MCP-8 compliance)."""
        from src.gramps_mcp.tools.search_basic import search_tool

        with pytest.raises(McpToolError, match="Entity type is required"):
            await search_tool({"gql": "test"})

    @pytest.mark.asyncio
    async def test_unsupported_entity_type_raises(self):
        """Unknown entity type raises McpToolError listing valid types."""
        from src.gramps_mcp.tools.search_basic import search_tool

        with pytest.raises(McpToolError, match="not supported for search"):
            await search_tool({"type": "unicorn", "gql": "test"})

    @pytest.mark.asyncio
    async def test_enum_entity_type_raises(self):
        """Enum-like types with .value that don't match raise McpToolError."""
        from src.gramps_mcp.tools.search_basic import search_tool

        class FakeEnum:
            value = "nonexistent"

        with pytest.raises(McpToolError, match="not supported for search"):
            await search_tool({"type": FakeEnum(), "gql": "test"})

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH, return_value=_mock_settings())
    async def test_person_dispatch(self, _settings, mock_client_cls):
        """type=person dispatches to search_person_tool."""
        from src.gramps_mcp.tools.search_basic import search_tool

        client_inst = _mock_client_instance()
        mock_client_cls.return_value = client_inst

        result = await search_tool({"type": "person", "gql": "test", "max_results": 1})
        assert isinstance(result[0], TextContent)


# ============================================================================
# search_text_tool
# ============================================================================


class TestFindAnythingTool:
    """Test search_text_tool response formatting."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(_SETTINGS_PATCH, return_value=_mock_settings()):
            yield

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    async def test_empty_results(self, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = _mock_client_instance()
        client_inst.make_api_call = AsyncMock(return_value=([], {"x-total-count": "0"}))
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert "No records found" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.format_search_result_by_type",
        new_callable=AsyncMock,
        return_value="* item\n",
    )
    @patch(_CLIENT_PATCH)
    async def test_list_response(self, mock_client_cls, mock_fmt):
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = _mock_client_instance()
        items = [{"object_type": "person", "object": {"handle": "h1"}}]
        client_inst.make_api_call = AsyncMock(
            return_value=(items, {"x-total-count": "1"})
        )
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert "Found 1 records" in result[0].text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.format_search_result_by_type",
        new_callable=AsyncMock,
        return_value="* item\n",
    )
    @patch(_CLIENT_PATCH)
    async def test_truncated_display(self, mock_client_cls, mock_fmt):
        """When total_count > displayed_count, show 'showing N'."""
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = _mock_client_instance()
        items = [{"object_type": "person", "object": {"handle": "h1"}}]
        client_inst.make_api_call = AsyncMock(
            return_value=(items, {"x-total-count": "100"})
        )
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        text = result[0].text
        assert "Found 100 records" in text
        assert "showing 1" in text

    @pytest.mark.asyncio
    @patch(
        "src.gramps_mcp.tools.search_basic.format_search_result_by_type",
        new_callable=AsyncMock,
        return_value="* item\n",
    )
    @patch(_CLIENT_PATCH)
    async def test_dict_response(self, mock_client_cls, mock_fmt):
        """Dict response with 'data' key parsed correctly."""
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = _mock_client_instance()
        resp_dict = {"data": [{"object_type": "event", "object": {"handle": "h1"}}]}
        client_inst.make_api_call = AsyncMock(
            return_value=(resp_dict, {"x-total-count": "1"})
        )
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert "Found 1 records" in result[0].text

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    async def test_skips_non_dict_items(self, mock_client_cls):
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = _mock_client_instance()
        items = ["not_a_dict", {"object_type": "person", "object": {"handle": "h1"}}]
        client_inst.make_api_call = AsyncMock(
            return_value=(items, {"x-total-count": "2"})
        )
        mock_client_cls.return_value = client_inst

        result = await search_text_tool({"query": "test"})
        assert isinstance(result[0], TextContent)

    @pytest.mark.asyncio
    @patch(_CLIENT_PATCH)
    async def test_missing_query_raises(self, mock_client_cls):
        """Missing required 'query' parameter raises McpToolError."""
        from src.gramps_mcp.tools.search_basic import search_text_tool

        client_inst = _mock_client_instance()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError, match="search"):
            await search_text_tool({})


# ============================================================================
# get_tool (search_details.py)
# ============================================================================


class TestGetTypeTool:
    """Test get_tool dispatch and gramps_id resolution."""

    @pytest.mark.asyncio
    async def test_unsupported_type_raises(self):
        """Unsupported entity type raises McpToolError (MCP-8 compliance)."""
        from src.gramps_mcp.tools.search_details import get_tool

        with pytest.raises(McpToolError, match="not supported for get"):
            await get_tool({"type": "unicorn", "handle": "h1"})

    @pytest.mark.asyncio
    async def test_no_handle_no_gramps_id_raises(self):
        """Neither handle nor gramps_id raises McpToolError."""
        from src.gramps_mcp.tools.search_details import get_tool

        with pytest.raises(McpToolError, match="Could not resolve"):
            await get_tool({"type": "event"})

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
            TextContent(type="text", text="* Event [resolved_handle] - E0001")
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
    async def test_gramps_id_not_resolved_raises(self, mock_find):
        """gramps_id that can't be resolved raises McpToolError."""
        from src.gramps_mcp.tools.search_details import get_tool

        mock_find.return_value = [TextContent(type="text", text="No events found")]
        with pytest.raises(McpToolError, match="Could not resolve"):
            await get_tool({"type": "event", "gramps_id": "E9999"})


# ============================================================================
# Individual get_*_tool missing-handle branches (parametrized)
# ============================================================================

# ============================================================================
# gql_hint (GQL discoverability helpers)
# ============================================================================


class TestGqlHint:
    """Test GQL smart hints for common person-search mistakes."""

    def test_bare_name_on_people(self):
        """'name ~ X' on people suggests primary_name.first_name."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", 'name ~ "Federico"')
        assert "primary_name.first_name" in hint
        assert "primary_name.surname_list[0].surname" in hint

    def test_bare_surname_on_people(self):
        """'surname ~ X' on people suggests correct path."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", 'surname ~ "Smith"')
        assert "primary_name.surname_list[0].surname" in hint

    def test_bare_firstname_on_people(self):
        """'firstname ~ X' on people suggests correct path."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", 'firstname ~ "John"')
        assert "primary_name.first_name" in hint

    def test_bare_first_name_on_people(self):
        """'first_name ~ X' (without dotted prefix) on people suggests correct path."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", 'first_name ~ "Maria"')
        assert "primary_name.first_name" in hint

    def test_correct_first_name_path_no_hint(self):
        """'primary_name.first_name ~ X' is correct — no hint."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", 'primary_name.first_name ~ "Federico"')
        assert hint == ""

    def test_correct_surname_path_no_hint(self):
        """'primary_name.surname_list[0].surname ~ X' is correct — no hint."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", 'primary_name.surname_list[0].surname ~ "Smith"')
        assert hint == ""

    def test_non_person_entity_name_no_hint(self):
        """'name ~ X' on places is valid — no hint."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        assert gql_hint("places", 'name ~ "Boston"') == ""
        assert gql_hint("sources", 'title ~ "Census"') == ""

    def test_empty_gql_no_hint(self):
        """Empty GQL string — no hint."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        assert gql_hint("people", "") == ""

    def test_unrelated_gql_no_hint(self):
        """GQL without mistake patterns — no hint."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        assert gql_hint("people", "gender = 1") == ""

    def test_name_at_start_of_gql(self):
        """Pattern works when 'name' is the very first token."""
        from src.gramps_mcp.tools._gql_hints import gql_hint

        hint = gql_hint("people", "name = John")
        assert "primary_name" in hint


class TestSearchEntitiesGqlHint:
    """Test that _search_entities includes GQL hint in empty results."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        with patch(_SETTINGS_PATCH, return_value=_mock_settings()):
            yield

    @pytest.mark.asyncio
    async def test_empty_results_with_hint(self):
        """Empty people search with bad GQL includes hint."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=[])
        handler = AsyncMock()

        result = await _search_entities(
            client,
            {"gql": 'name ~ "Federico"'},
            BaseGetMultipleParams,
            "GET_PEOPLE",
            "people",
            handler,
        )
        text = result[0].text
        assert "No people found" in text
        assert "Hint:" in text
        assert "primary_name" in text

    @pytest.mark.asyncio
    async def test_empty_results_without_hint(self):
        """Empty people search with correct GQL has no hint."""
        from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
        from src.gramps_mcp.tools.search_basic import _search_entities

        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value=[])
        handler = AsyncMock()

        result = await _search_entities(
            client,
            {"gql": 'primary_name.first_name ~ "Federico"'},
            BaseGetMultipleParams,
            "GET_PEOPLE",
            "people",
            handler,
        )
        text = result[0].text
        assert "No people found" in text
        assert "Hint:" not in text


class TestSearchToolDescription:
    """Test that search tool description includes person name hint."""

    def test_description_contains_person_name_hint(self):
        """Search tool description must mention primary_name paths."""
        from src.gramps_mcp.operations import OPERATION_REGISTRY

        desc = OPERATION_REGISTRY["search"].description
        assert "primary_name.first_name" in desc
        assert "primary_name.surname_list[0].surname" in desc


# ============================================================================
# Individual get_*_tool missing-handle branches (parametrized)
# ============================================================================

_GET_TOOL_MISSING_HANDLE_CASES = [
    ("get_event_tool", "event details"),
    ("get_place_tool", "place details"),
    ("get_source_tool", "source details"),
    ("get_citation_tool", "citation details"),
    ("get_note_tool", "note details"),
    ("get_media_tool", "media details"),
    ("get_repository_tool", "repository details"),
    ("get_person_tool", "person details"),
    ("get_family_tool", "family details"),
]


class TestGetToolsMissingHandle:
    """Test that get_*_tool functions raise on missing handle."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name, match_text", _GET_TOOL_MISSING_HANDLE_CASES)
    @patch(
        "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient",
        side_effect=lambda: AsyncMock(close=AsyncMock()),
    )
    async def test_missing_handle_raises(self, _, tool_name, match_text):
        import src.gramps_mcp.tools.search_details as mod

        tool_func = getattr(mod, tool_name)
        with pytest.raises(McpToolError, match=match_text):
            await tool_func({})
