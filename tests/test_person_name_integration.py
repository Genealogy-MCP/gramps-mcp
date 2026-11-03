# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for Name key validation on upsert_person (#113).

A bare "surname" key in primary_name must fail before anything reaches the
API, so no person is created. A name read back from the API, every Gramps key
included, must still be accepted on update.
"""

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration


async def _call(api_call: ApiCalls, **kwargs):
    """Make one Gramps Web API call with a fresh client.

    Args:
        api_call (ApiCalls): The endpoint to call.
        **kwargs: Forwarded to make_api_call.

    Returns:
        The decoded response.
    """
    client = GrampsWebAPIClient()
    try:
        return await client.make_api_call(
            api_call=api_call, tree_id=get_settings().gramps_tree_id, **kwargs
        )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bare_surname_is_rejected_and_creates_nothing():
    """The production payload errors with the surname_list hint, no record."""
    first_name = f"{TEST_PREFIX}NameStraySurname"

    with pytest.raises(McpToolError, match="surname_list"):
        await UPSERT_HANDLERS["person"](
            {
                "primary_name": {"first_name": first_name, "surname": "Sparks"},
                "gender": 2,
            }
        )

    found = await _call(
        ApiCalls.GET_PEOPLE,
        params=BaseGetMultipleParams(
            gql=f'primary_name.first_name = "{first_name}"', keys="handle"
        ),
    )
    assert found == [], "A person was created despite the invalid name"


@pytest.mark.asyncio
async def test_name_read_back_from_the_api_is_accepted_on_update():
    """A GET-shaped primary_name, _class and all, round-trips through a PUT."""
    result = await UPSERT_HANDLERS["person"](
        {
            "primary_name": {
                "first_name": f"{TEST_PREFIX}NameRoundTrip",
                "surname_list": [{"surname": f"{TEST_PREFIX}Testing"}],
            },
            "gender": 2,
        }
    )
    handle = extract_handle(result[0].text)
    stored = await _call(ApiCalls.GET_PERSON, handle=handle)

    name = dict(stored["primary_name"], nick=f"{TEST_PREFIX}Nick")
    update = await UPSERT_HANDLERS["person"]({"handle": handle, "primary_name": name})
    assert "Error:" not in update[0].text, update[0].text

    updated = await _call(ApiCalls.GET_PERSON, handle=handle)
    assert updated["primary_name"]["nick"] == f"{TEST_PREFIX}Nick"
    assert updated["primary_name"]["surname_list"][0]["surname"] == (
        f"{TEST_PREFIX}Testing"
    )
