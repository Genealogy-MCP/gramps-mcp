# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for the parameter fields added in issue #75.

Each field below was accepted by the Gramps Web API but undeclared on its
upsert parameter model, so a caller passing it got a success message and a
silent drop. These tests assert the value survives a real create and a real
update against the API.

The LDS ordinance shapes here use integer type and status on purpose. The
server answers HTTP 500 for the name strings that every other typed enum in
this codebase accepts.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.tools import (
    upsert_person_tool,
    upsert_repository_tool,
    upsert_source_tool,
)

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _fetch(api_call: ApiCalls, handle: str) -> dict:
    """GET one entity from the API by handle.

    Args:
        api_call (ApiCalls): The GET endpoint to call.
        handle (str): The entity's handle.

    Returns:
        dict: The stored entity.
    """
    client = GrampsWebAPIClient()
    try:
        return await client.make_api_call(
            api_call=api_call,
            tree_id=get_settings().gramps_tree_id,
            handle=handle,
        )
    finally:
        await client.close()


def _handle_of(result) -> str:
    """Assert a tool call succeeded and return the new entity's handle.

    Args:
        result: The tool's returned content list.

    Returns:
        str: The entity handle parsed out of the success message.
    """
    text = result[0].text
    assert "Error:" not in text, f"Expected success: {text}"
    return extract_handle(text)


def _person_payload(label: str, **extra) -> dict:
    """Build a minimal valid upsert_person payload.

    Args:
        label (str): Distinguishing label for the person's first name.
        **extra: Additional fields forwarded to upsert_person.

    Returns:
        dict: The payload.
    """
    payload = {
        "primary_name": {
            "first_name": f"{TEST_PREFIX}{label}",
            "surname_list": [{"surname": f"{TEST_PREFIX}Testing", "primary": True}],
        },
        "gender": 2,
    }
    payload.update(extra)
    return payload


class TestSourceAbbrev:
    """SourceSaveParams.abbrev reaches the API."""

    @pytest.mark.asyncio
    async def test_create_source_with_abbrev(self):
        """abbrev passed on create is stored."""
        handle = _handle_of(
            await upsert_source_tool(
                {"title": f"{TEST_PREFIX}Abbrev Create", "abbrev": f"{TEST_PREFIX}AC"}
            )
        )
        stored = await _fetch(ApiCalls.GET_SOURCE, handle)
        assert stored["abbrev"] == f"{TEST_PREFIX}AC"

    @pytest.mark.asyncio
    async def test_update_source_abbrev(self):
        """abbrev passed on update overwrites the stored value."""
        handle = _handle_of(
            await upsert_source_tool({"title": f"{TEST_PREFIX}Abbrev Update"})
        )
        result = await upsert_source_tool(
            {"handle": handle, "abbrev": f"{TEST_PREFIX}AU"}
        )
        assert "Error:" not in result[0].text, result[0].text

        stored = await _fetch(ApiCalls.GET_SOURCE, handle)
        assert stored["abbrev"] == f"{TEST_PREFIX}AU"


class TestRepositoryAddressList:
    """RepositoryData.address_list reaches the API."""

    @pytest.mark.asyncio
    async def test_create_repository_with_address(self):
        """address_list passed on create is stored."""
        handle = _handle_of(
            await upsert_repository_tool(
                {
                    "name": f"{TEST_PREFIX}Addr Create",
                    "type": "Archive",
                    "address_list": [
                        {"street": "1 Main St", "city": "Boston", "country": "USA"}
                    ],
                }
            )
        )
        stored = await _fetch(ApiCalls.GET_REPOSITORY, handle)
        assert [(a["street"], a["city"]) for a in stored["address_list"]] == [
            ("1 Main St", "Boston")
        ]

    @pytest.mark.asyncio
    async def test_update_repository_address_merges_by_default(self):
        """A second address appends under the default list_mode='merge'."""
        handle = _handle_of(
            await upsert_repository_tool(
                {
                    "name": f"{TEST_PREFIX}Addr Merge",
                    "type": "Archive",
                    "address_list": [{"street": "1 Main St", "city": "Boston"}],
                }
            )
        )
        result = await upsert_repository_tool(
            {
                "handle": handle,
                "address_list": [{"street": "2 Elm St", "city": "Salem"}],
            }
        )
        assert "Error:" not in result[0].text, result[0].text

        stored = await _fetch(ApiCalls.GET_REPOSITORY, handle)
        assert [a["street"] for a in stored["address_list"]] == [
            "1 Main St",
            "2 Elm St",
        ]

    @pytest.mark.asyncio
    async def test_repeated_repository_address_does_not_duplicate(self):
        """Re-sending the same address leaves one entry (merge dedups)."""
        address = {"street": "3 Oak Ave", "city": "Concord"}
        handle = _handle_of(
            await upsert_repository_tool(
                {
                    "name": f"{TEST_PREFIX}Addr Idempotent",
                    "type": "Archive",
                    "address_list": [address],
                }
            )
        )
        result = await upsert_repository_tool(
            {"handle": handle, "address_list": [address]}
        )
        assert "Error:" not in result[0].text, result[0].text

        stored = await _fetch(ApiCalls.GET_REPOSITORY, handle)
        assert [a["street"] for a in stored["address_list"]] == ["3 Oak Ave"]


class TestPersonAddressList:
    """PersonData.address_list reaches the API."""

    @pytest.mark.asyncio
    async def test_create_person_with_address(self):
        """address_list passed on create is stored."""
        handle = _handle_of(
            await upsert_person_tool(
                _person_payload(
                    "PersonAddrCreate",
                    address_list=[{"street": "4 Pine Rd", "city": "Lowell"}],
                )
            )
        )
        stored = await _fetch(ApiCalls.GET_PERSON, handle)
        assert [(a["street"], a["city"]) for a in stored["address_list"]] == [
            ("4 Pine Rd", "Lowell")
        ]

    @pytest.mark.asyncio
    async def test_update_person_address_merges_by_default(self):
        """A second address appends under the default list_mode='merge'."""
        handle = _handle_of(
            await upsert_person_tool(
                _person_payload(
                    "PersonAddrMerge",
                    address_list=[{"street": "4 Pine Rd", "city": "Lowell"}],
                )
            )
        )
        result = await upsert_person_tool(
            {
                "handle": handle,
                "address_list": [{"street": "5 Cedar Ln", "city": "Quincy"}],
            }
        )
        assert "Error:" not in result[0].text, result[0].text

        stored = await _fetch(ApiCalls.GET_PERSON, handle)
        assert [a["street"] for a in stored["address_list"]] == [
            "4 Pine Rd",
            "5 Cedar Ln",
        ]


class TestPersonLdsOrdList:
    """PersonData.lds_ord_list reaches the API."""

    @pytest.mark.asyncio
    async def test_create_person_with_lds_ordinance(self):
        """lds_ord_list passed on create is stored."""
        handle = _handle_of(
            await upsert_person_tool(
                _person_payload(
                    "LdsCreate",
                    lds_ord_list=[{"type": 0, "status": 1, "temple": "LOGAN"}],
                )
            )
        )
        stored = await _fetch(ApiCalls.GET_PERSON, handle)
        assert [
            (o["type"], o["status"], o["temple"]) for o in stored["lds_ord_list"]
        ] == [(0, 1, "LOGAN")]

    @pytest.mark.asyncio
    async def test_update_person_lds_ordinance_merges_by_default(self):
        """A second ordinance appends under the default list_mode='merge'."""
        handle = _handle_of(
            await upsert_person_tool(
                _person_payload(
                    "LdsMerge",
                    lds_ord_list=[{"type": 0, "status": 1, "temple": "LOGAN"}],
                )
            )
        )
        result = await upsert_person_tool(
            {
                "handle": handle,
                "lds_ord_list": [{"type": 1, "status": 1, "temple": "SLAKE"}],
            }
        )
        assert "Error:" not in result[0].text, result[0].text

        stored = await _fetch(ApiCalls.GET_PERSON, handle)
        assert [(o["type"], o["temple"]) for o in stored["lds_ord_list"]] == [
            (0, "LOGAN"),
            (1, "SLAKE"),
        ]

    @pytest.mark.asyncio
    async def test_lds_ordinance_name_string_is_rejected(self):
        """The API rejects a name string for type; only integers work.

        Guards the field description. If a future API version starts accepting
        "Baptism" here, this test fails and the description needs updating.
        """
        with pytest.raises(Exception) as excinfo:
            await upsert_person_tool(
                _person_payload(
                    "LdsNameString",
                    lds_ord_list=[{"type": "Baptism", "status": "Completed"}],
                )
            )
        assert "500" in str(excinfo.value)
