# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for person_ref_list validation in upsert_person_tool (issue #40).

Mirrors tests/test_citation_validation.py: a mocked client checks that each
association's `ref` resolves to an existing person, self-references are
rejected, and valid refs pass through to the write.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.data_management import upsert_person_tool


def _mock_settings():
    return type("Settings", (), {"gramps_tree_id": "tree1"})()


class TestPersonRefValidation:
    """person_ref_list ref validation in upsert_person_tool."""

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_unknown_ref_rejected_names_handle(self, _settings, mock_client_cls):
        from src.gramps_mcp.client import GrampsAPIError

        client_inst = AsyncMock()

        async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_PERSON":
                raise GrampsAPIError("Record not found at /people/ghost.")
            return [{"new": {"handle": "p1", "gramps_id": "I0001"}}]

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        with pytest.raises(McpToolError, match="ghost"):
            await upsert_person_tool(
                {
                    "primary_name": {"first_name": "A", "surname_list": []},
                    "gender": 1,
                    "person_ref_list": [{"ref": "ghost", "rel": "Cousin"}],
                }
            )

    @pytest.mark.asyncio
    async def test_self_reference_rejected(self):
        with pytest.raises(McpToolError, match="(?i)itself"):
            await upsert_person_tool(
                {
                    "handle": "p1",
                    "person_ref_list": [{"ref": "p1", "rel": "Cousin"}],
                }
            )

    @pytest.mark.asyncio
    @patch("src.gramps_mcp.tools.data_management.GrampsWebAPIClient")
    @patch(
        "src.gramps_mcp.tools.data_management.get_settings",
        return_value=_mock_settings(),
    )
    @patch("src.gramps_mcp.tools._data_helpers.FORMATTER_DISPATCH", {})
    async def test_valid_refs_pass_through(self, _settings, mock_client_cls):
        client_inst = AsyncMock()

        async def mock_api_call(
            api_call, tree_id=None, handle=None, params=None, **kwargs
        ):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_PERSON":
                return {"handle": handle, "gramps_id": "I0002"}
            return [{"new": {"handle": "p1", "gramps_id": "I0001"}}]

        client_inst.make_api_call = AsyncMock(side_effect=mock_api_call)
        client_inst.close = AsyncMock()
        mock_client_cls.return_value = client_inst

        result = await upsert_person_tool(
            {
                "primary_name": {"first_name": "A", "surname_list": []},
                "gender": 1,
                "person_ref_list": [
                    {"ref": "p2", "rel": "Cousin"},
                    {"ref": "p3", "rel": "Friend"},
                ],
            }
        )
        assert "created" in result[0].text.lower() or "I0001" in result[0].text
