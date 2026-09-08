# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for person-level citation_list (#76).

Covers the field declaration on PersonData, its presence in the API payload on
create and update, and the list_mode semantics the client's existing PUT merge
applies to a plain list of citation handles. No network is used: the client's
transport is mocked so the PUT body can be inspected directly.
"""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.people_params import PersonData


class TestPersonDataCitationList:
    """PersonData declares citation_list and serializes it."""

    def test_field_is_declared_and_optional(self) -> None:
        """citation_list exists on PersonData and is not required."""
        field = PersonData.model_fields.get("citation_list")
        assert field is not None, "PersonData is missing citation_list"
        assert not field.is_required()
        assert field.description, "citation_list needs a description (MCP-4)"

    def test_payload_on_create(self) -> None:
        """A create payload carries citation_list through to the API body."""
        params = PersonData(
            primary_name={"first_name": "Ada"},
            gender=0,
            citation_list=["c1", "c2"],
        )
        assert params.to_api_payload()["citation_list"] == ["c1", "c2"]

    def test_payload_on_update(self) -> None:
        """An update payload carries citation_list through to the API body."""
        params = PersonData(handle="p1", citation_list=["c3"])
        assert params.to_api_payload()["citation_list"] == ["c3"]

    def test_omitted_when_not_supplied(self) -> None:
        """No citation_list key is sent when the caller did not supply one."""
        params = PersonData(handle="p1", gender=1)
        assert "citation_list" not in params.to_api_payload()


async def _put_body(stored: List[str], sent: Dict[str, Any]) -> Dict[str, Any]:
    """Run a PUT_PERSON through the client and return the body it would send.

    Args:
        stored (List[str]): citation_list already on the stored person.
        sent (Dict[str, Any]): The caller's update payload.

    Returns:
        Dict[str, Any]: The JSON body the client sends to the API.
    """
    client = GrampsWebAPIClient()
    client.auth_manager = MagicMock()
    client.auth_manager.get_token = AsyncMock()
    client.auth_manager.get_headers = MagicMock(
        return_value={"Authorization": "Bearer test"}
    )
    client.auth_manager.client = MagicMock()
    client.auth_manager.close = AsyncMock()

    existing = {"handle": "p1", "gramps_id": "I0001", "citation_list": stored}
    with patch.object(client, "_make_request", new_callable=AsyncMock) as request:
        request.side_effect = [existing, {"success": True}]
        await client.make_api_call(
            api_call=ApiCalls.PUT_PERSON,
            params=PersonData(**sent),
            tree_id="test_tree",
            handle="p1",
        )
        put_call = request.call_args_list[1]
        return put_call.kwargs["json_data"]


class TestPersonCitationListMode:
    """list_mode semantics for the person citation_list on PUT."""

    @pytest.mark.asyncio
    async def test_merge_appends_new_handles(self) -> None:
        """Default merge appends handles not already stored."""
        body = await _put_body(["c1"], {"handle": "p1", "citation_list": ["c2"]})
        assert body["citation_list"] == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_merge_dedups_existing_handles(self) -> None:
        """Re-sending a stored handle does not duplicate it."""
        body = await _put_body(
            ["c1", "c2"], {"handle": "p1", "citation_list": ["c2", "c3"]}
        )
        assert body["citation_list"] == ["c1", "c2", "c3"]

    @pytest.mark.asyncio
    async def test_replace_overwrites_stored_list(self) -> None:
        """replace mode overwrites the stored list wholesale."""
        body = await _put_body(
            ["c1", "c2"],
            {"handle": "p1", "citation_list": ["c3"], "list_mode": "replace"},
        )
        assert body["citation_list"] == ["c3"]

    @pytest.mark.asyncio
    async def test_list_mode_is_not_sent_to_the_api(self) -> None:
        """The internal list_mode field never reaches the API body."""
        body = await _put_body(["c1"], {"handle": "p1", "citation_list": ["c2"]})
        assert "list_mode" not in body
