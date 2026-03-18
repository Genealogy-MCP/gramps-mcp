"""
Unit tests for data management tools — CRUD helpers, delete, tag, and media tools.

Tests mock GrampsWebAPIClient to avoid network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from src.gramps_mcp.tools._data_helpers import (
    _extract_entity_data,
    _format_save_response,
    _handle_crud_operation,
)
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.data_management import (
    upsert_family_tool,
    upsert_repository_tool,
)
from src.gramps_mcp.tools.data_management_delete import delete_tool, upsert_tag_tool
from src.gramps_mcp.tools.data_management_media import upsert_media_tool


def _mock_settings():
    """Return a mock settings object."""
    return type("Settings", (), {"gramps_tree_id": "tree1"})()


# ---------------------------------------------------------------------------
# _extract_entity_data  (pure function)
# ---------------------------------------------------------------------------


class TestExtractEntityData:
    """Test _extract_entity_data response parsing."""

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError, match="empty response"):
            _extract_entity_data(None)

    def test_empty_dict_raises_value_error(self):
        with pytest.raises(ValueError, match="empty response"):
            _extract_entity_data({})

    def test_empty_list_raises_value_error(self):
        with pytest.raises(ValueError, match="empty response"):
            _extract_entity_data([])

    def test_standard_list_with_new(self):
        result = [{"new": {"handle": "h1", "gramps_id": "I001"}}]
        assert _extract_entity_data(result) == {"handle": "h1", "gramps_id": "I001"}

    def test_dict_returned_as_is(self):
        result = {"handle": "h1", "gramps_id": "I001"}
        assert _extract_entity_data(result) == {"handle": "h1", "gramps_id": "I001"}

    def test_family_creation_finds_family_class(self):
        result = [
            {"new": {"_class": "Person", "handle": "p1"}},
            {"new": {"_class": "Family", "handle": "f1", "gramps_id": "F001"}},
        ]
        entity = _extract_entity_data(result, entity_type="family")
        assert entity["handle"] == "f1"
        assert entity["_class"] == "Family"

    def test_family_creation_no_family_class_falls_back(self):
        result = [
            {"new": {"_class": "Person", "handle": "p1", "gramps_id": "I001"}},
            {"new": {"_class": "Person", "handle": "p2"}},
        ]
        entity = _extract_entity_data(result, entity_type="family")
        assert entity["handle"] == "p1"

    def test_list_without_new_key(self):
        """List items without 'new' key return the first entry."""
        result = [{"handle": "h1"}]
        assert _extract_entity_data(result) == {"handle": "h1"}


# ---------------------------------------------------------------------------
# _format_save_response
# ---------------------------------------------------------------------------


class TestFormatSaveResponse:
    """Test _format_save_response with mocked formatters."""

    @pytest.mark.asyncio
    async def test_known_entity_with_formatter(self):
        mock_formatter = AsyncMock(return_value="* **Person I001** details\n")
        client = AsyncMock()

        with patch(
            "src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH",
            {"person": mock_formatter},
        ):
            result = await _format_save_response(
                client,
                {"handle": "h1", "gramps_id": "I001"},
                "person",
                "created",
                "tree1",
            )

        assert "Successfully created person" in result
        assert "I001" in result
        mock_formatter.assert_awaited_once_with(client, "tree1", "h1")

    @pytest.mark.asyncio
    async def test_unknown_entity_type_fallback(self):
        client = AsyncMock()

        with patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {}):
            result = await _format_save_response(
                client,
                {"handle": "h1", "gramps_id": "T001"},
                "tag",
                "updated",
                "tree1",
            )

        assert "Successfully updated tag" in result
        assert "T001" in result

    @pytest.mark.asyncio
    async def test_formatter_raises_exception_fallback(self):
        mock_formatter = AsyncMock(side_effect=RuntimeError("format failed"))
        client = AsyncMock()

        with patch(
            "src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH",
            {"event": mock_formatter},
        ):
            result = await _format_save_response(
                client,
                {"handle": "h1", "gramps_id": "E001"},
                "event",
                "created",
                "tree1",
            )

        assert "Successfully created event" in result
        assert "E001" in result
        assert "Handle" in result


# ---------------------------------------------------------------------------
# _handle_crud_operation
# ---------------------------------------------------------------------------


class TestHandleCrudOperation:
    """Test _handle_crud_operation create/update paths."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools._data_helpers.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools._data_helpers.get_settings",
        return_value=_mock_settings(),
    )
    @patch(
        "src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH",
        {},
    )
    async def test_create_path(self, _settings, mock_client_cls):
        """No handle in params triggers POST (create)."""
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.event_params import EventSaveParams

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value=[{"new": {"handle": "e1", "gramps_id": "E001"}}]
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await _handle_crud_operation(
            {"type": "Birth", "citation_list": []},
            "event",
            ApiCalls.POST_EVENTS,
            ApiCalls.PUT_EVENT,
            EventSaveParams,
        )

        assert isinstance(result[0], TextContent)
        assert "created" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools._data_helpers.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools._data_helpers.get_settings",
        return_value=_mock_settings(),
    )
    @patch(
        "src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH",
        {},
    )
    async def test_update_path(self, _settings, mock_client_cls):
        """Handle in params triggers PUT (update)."""
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.event_params import EventSaveParams

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "e1", "gramps_id": "E001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await _handle_crud_operation(
            {"handle": "e1", "type": "Birth", "citation_list": []},
            "event",
            ApiCalls.POST_EVENTS,
            ApiCalls.PUT_EVENT,
            EventSaveParams,
        )

        assert isinstance(result[0], TextContent)
        assert "updated" in result[0].text

    @pytest.mark.asyncio
    async def test_validation_error_raises_mcp_error(self):
        """Invalid params raise McpToolError."""
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.event_params import EventSaveParams

        with pytest.raises(McpToolError):
            await _handle_crud_operation(
                {"invalid_field_xyz": True},
                "event",
                ApiCalls.POST_EVENTS,
                ApiCalls.PUT_EVENT,
                EventSaveParams,
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools._data_helpers.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools._data_helpers.get_settings",
        return_value=_mock_settings(),
    )
    async def test_api_error_raises_mcp_error(self, _settings, mock_client_cls):
        """GrampsAPIError during API call wraps as McpToolError."""
        from src.gramps_mcp.client import GrampsAPIError
        from src.gramps_mcp.models.api_calls import ApiCalls
        from src.gramps_mcp.models.parameters.event_params import EventSaveParams

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            side_effect=GrampsAPIError("Record not found at /events/bad")
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError, match="event save"):
            await _handle_crud_operation(
                {"type": "Birth"},
                "event",
                ApiCalls.POST_EVENTS,
                ApiCalls.PUT_EVENT,
                EventSaveParams,
            )


# ---------------------------------------------------------------------------
# delete_tool
# ---------------------------------------------------------------------------


class TestDeleteTool:
    """Test delete_tool dispatch and error handling."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_delete.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_delete.get_settings",
        return_value=_mock_settings(),
    )
    async def test_delete_success(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(return_value={})
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await delete_tool({"type": "person", "handle": "p1"})
        assert "Successfully deleted" in result[0].text
        assert "person" in result[0].text
        assert "p1" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_delete.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_delete.get_settings",
        return_value=_mock_settings(),
    )
    async def test_delete_api_error(self, _settings, mock_client_cls):
        from src.gramps_mcp.client import GrampsAPIError

        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(side_effect=GrampsAPIError("Not found"))
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await delete_tool({"type": "event", "handle": "e1"})

    @pytest.mark.asyncio
    async def test_delete_invalid_params(self):
        """Missing required params raises McpToolError."""
        with pytest.raises(McpToolError):
            await delete_tool({})

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_delete.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_delete.get_settings",
        return_value=_mock_settings(),
    )
    async def test_delete_tag_uses_bulk(self, _settings, mock_client_cls):
        """TAG enum value routes through bulk_delete, not standard DELETE."""
        client_inst = AsyncMock()
        client_inst.bulk_delete = AsyncMock(return_value={})
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await delete_tool({"type": "tag", "handle": "t1"})
        assert "Successfully deleted" in result[0].text
        assert "tag" in result[0].text
        client_inst.bulk_delete.assert_called_once_with(
            items=[{"_class": "Tag", "handle": "t1"}], tree_id="tree1"
        )


# ---------------------------------------------------------------------------
# upsert_family_tool
# ---------------------------------------------------------------------------


class TestUpsertFamilyTool:
    """Test upsert_family_tool create and update paths."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_create_family(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value=[
                {"new": {"_class": "Family", "handle": "f1", "gramps_id": "F001"}}
            ]
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_family_tool({"father_handle": "p1"})
        assert isinstance(result[0], TextContent)
        assert "created" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_update_family(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "f1", "gramps_id": "F001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_family_tool({"handle": "f1", "father_handle": "p1"})
        assert "updated" in result[0].text


# ---------------------------------------------------------------------------
# upsert_repository_tool
# ---------------------------------------------------------------------------


class TestUpsertRepositoryTool:
    """Test upsert_repository_tool create and update paths."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_create_repository(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value=[{"new": {"handle": "r1", "gramps_id": "R001"}}]
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_repository_tool({"name": "Test Repo", "type": "Library"})
        assert "created" in result[0].text

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_update_repository(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "r1", "gramps_id": "R001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_repository_tool(
            {"handle": "r1", "name": "Updated Repo", "type": "Archive"}
        )
        assert "updated" in result[0].text


# ---------------------------------------------------------------------------
# upsert_tag_tool
# ---------------------------------------------------------------------------


class TestUpsertTagTool:
    """Test upsert_tag_tool create and update paths."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_delete.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_delete.get_settings",
        return_value=_mock_settings(),
    )
    async def test_create_tag(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value=[
                {
                    "new": {
                        "handle": "t1",
                        "name": "Research",
                        "color": "#FF0000",
                        "priority": 1,
                    }
                }
            ]
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_tag_tool({"name": "Research", "color": "#FF0000"})
        assert "created" in result[0].text
        assert "Research" in result[0].text

    @pytest.mark.asyncio
    async def test_update_tag_raises_error(self):
        """Tag updates are not supported in API 3.x — should raise McpToolError."""
        with pytest.raises(McpToolError, match="not supported"):
            await upsert_tag_tool(
                {"handle": "t1", "name": "Updated", "color": "#00FF00"}
            )


# ---------------------------------------------------------------------------
# upsert_media_tool
# ---------------------------------------------------------------------------


class TestUpsertMediaTool:
    """Test upsert_media_tool update path (create requires real file)."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_update_media(self, _settings, mock_client_cls):
        client_inst = AsyncMock()
        client_inst.make_api_call = AsyncMock(
            return_value={"handle": "m1", "gramps_id": "O001"}
        )
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_media_tool({"handle": "m1", "desc": "Updated photo"})
        assert "updated" in result[0].text

    @pytest.mark.asyncio
    async def test_create_media_no_file_raises(self):
        """Creating media without file_location raises error."""
        with pytest.raises(McpToolError):
            await upsert_media_tool({"desc": "No file"})

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management_media.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management_media.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_create_media_file_not_found(self, _settings, mock_client_cls):
        """Creating media with nonexistent file raises error."""
        client_inst = AsyncMock()
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError):
            await upsert_media_tool(
                {"file_location": "/nonexistent/file.jpg", "desc": "test"}
            )
