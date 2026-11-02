"""
Unit tests for citation source_handle validation in UPSERT_HANDLERS["citation"].

Tests verify that source_handle existence is checked before writing,
and that self-referencing citations are rejected.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS
from tests._resource_shim import route_call_resource


def _mock_settings():
    """Return a mock settings object."""
    return type("Settings", (), {"gramps_tree_id": "tree1"})()


class TestCitationSourceHandleValidation:
    """Test source_handle validation in UPSERT_HANDLERS["citation"]."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.upsert_table.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.upsert_table.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_invalid_source_handle_rejected(self, _settings, mock_client_cls):
        """upsert_citation rejects a source_handle that doesn't exist."""
        from src.gramps_mcp.client import GrampsAPIError

        client_inst = AsyncMock()

        async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_SOURCE":
                raise GrampsAPIError("Record not found at /sources/nonexistent_handle.")
            return [{"new": {"handle": "c1", "gramps_id": "C001"}}]

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst
        route_call_resource(client_inst)

        with pytest.raises(McpToolError, match="(?i)source.*not found"):
            await UPSERT_HANDLERS["citation"](
                {"source_handle": "nonexistent_handle", "page": "p. 42"}
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.upsert_table.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.upsert_table.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_valid_source_handle_accepted(self, _settings, mock_client_cls):
        """upsert_citation succeeds when source_handle references an existing source."""
        client_inst = AsyncMock()

        async def mock_api_call(
            api_call, tree_id=None, handle=None, params=None, **kwargs
        ):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_SOURCE":
                return {"handle": "s1", "gramps_id": "S001", "title": "Test Source"}
            return [{"new": {"handle": "c1", "gramps_id": "C001"}}]

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst
        route_call_resource(client_inst)

        result = await UPSERT_HANDLERS["citation"](
            {"source_handle": "s1", "page": "p. 42"}
        )
        assert "created" in result[0].text.lower() or "C001" in result[0].text

    @pytest.mark.asyncio
    async def test_self_reference_rejected(self):
        """Citation's source_handle must not equal its own handle."""
        with pytest.raises(McpToolError, match="cannot reference itself"):
            await UPSERT_HANDLERS["citation"](
                {
                    "handle": "same_handle",
                    "source_handle": "same_handle",
                    "page": "p. 1",
                }
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.upsert_table.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.upsert_table.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_source_returns_404_rejected(self, _settings, mock_client_cls):
        """upsert_citation rejects when GET /sources/{handle} returns 404."""
        from src.gramps_mcp.client import GrampsAPIError

        client_inst = AsyncMock()

        async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_SOURCE":
                raise GrampsAPIError("Record not found at /sources/bad_handle.")
            return [{"new": {"handle": "c1", "gramps_id": "C001"}}]

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst
        route_call_resource(client_inst)

        with pytest.raises(McpToolError, match="(?i)source.*not found"):
            await UPSERT_HANDLERS["citation"](
                {"source_handle": "bad_handle", "page": "p. 10"}
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.upsert_table.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.upsert_table.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_source_returns_empty_rejected(self, _settings, mock_client_cls):
        """upsert_citation rejects when GET /sources/{handle} returns empty/falsy."""
        client_inst = AsyncMock()

        async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_SOURCE":
                return {}
            return [{"new": {"handle": "c1", "gramps_id": "C001"}}]

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst
        route_call_resource(client_inst)

        with pytest.raises(McpToolError, match="(?i)source.*not found"):
            await UPSERT_HANDLERS["citation"](
                {"source_handle": "empty_handle", "page": "p. 10"}
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.upsert_table.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.upsert_table.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_update_citation_also_validates_source(
        self, _settings, mock_client_cls
    ):
        """Updating an existing citation still validates source_handle."""
        from src.gramps_mcp.client import GrampsAPIError

        client_inst = AsyncMock()

        async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_SOURCE":
                raise GrampsAPIError("Record not found at /sources/bad_src.")
            return {"handle": "c1", "gramps_id": "C001"}

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst
        route_call_resource(client_inst)

        with pytest.raises(McpToolError, match="(?i)source.*not found"):
            await UPSERT_HANDLERS["citation"](
                {
                    "handle": "c1",
                    "source_handle": "bad_src",
                    "page": "p. 10",
                }
            )
