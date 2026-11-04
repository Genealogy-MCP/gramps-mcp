# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration tests for a create that answers 5xx (#106) or times out (#130).

Gramps Web commits a new record before it updates the search index, and
answers 500 when that later step fails, for example with the celery broker
down. The client below sends the real POST and then reports a 500, which
reproduces the observed failure without stopping a container. The other
client reports a 500 without sending the POST, the case where nothing was
written. The timeout clients do the same with a read timeout, and the
connect-error client fails the POST unsent and counts the GETs that follow.
"""

import pytest

from src.gramps_mcp.client import GrampsAPIError, GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.base_params import BaseGetMultipleParams
from src.gramps_mcp.tools import upsert_table
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS

from .conftest import TEST_PREFIX, extract_handle

pytestmark = pytest.mark.integration

_SERVER_ERROR = "Server error (500) at people/."
_TIMEOUT = GrampsAPIError("Request timeout: read.", request_sent=True)


class _CommitThen500(GrampsWebAPIClient):
    """Client whose POSTs reach the server and then report HTTP 500."""

    async def _make_request(self, method, url, *args, **kwargs):
        """
        Send the request; turn a POST's reply into a 500.

        Args:
            method (str): HTTP verb.
            url (str): Request URL.
            *args: Forwarded to the real request.
            **kwargs: Forwarded to the real request.

        Returns:
            Any: The real response for every verb but POST.
        """
        response = await super()._make_request(method, url, *args, **kwargs)
        if method == "POST":
            raise GrampsAPIError(_SERVER_ERROR, status_code=500)
        return response


class _500BeforeWrite(GrampsWebAPIClient):
    """Client whose POSTs report HTTP 500 without reaching the server."""

    async def _make_request(self, method, url, *args, **kwargs):
        """
        Fail a POST unsent; send every other request.

        Args:
            method (str): HTTP verb.
            url (str): Request URL.
            *args: Forwarded to the real request.
            **kwargs: Forwarded to the real request.

        Returns:
            Any: The real response for every verb but POST.
        """
        if method == "POST":
            raise GrampsAPIError(_SERVER_ERROR, status_code=500)
        return await super()._make_request(method, url, *args, **kwargs)


class _CommitThenTimeout(GrampsWebAPIClient):
    """Client whose POSTs reach the server and then time out reading."""

    async def _make_request(self, method, url, *args, **kwargs):
        """
        Send the request; turn a POST's reply into a read timeout.

        Args:
            method (str): HTTP verb.
            url (str): Request URL.
            *args: Forwarded to the real request.
            **kwargs: Forwarded to the real request.

        Returns:
            Any: The real response for every verb but POST.
        """
        response = await super()._make_request(method, url, *args, **kwargs)
        if method == "POST":
            raise _TIMEOUT
        return response


class _TimeoutBeforeWrite(GrampsWebAPIClient):
    """Client whose POSTs time out without reaching the server."""

    async def _make_request(self, method, url, *args, **kwargs):
        """
        Time a POST out unsent; send every other request.

        Args:
            method (str): HTTP verb.
            url (str): Request URL.
            *args: Forwarded to the real request.
            **kwargs: Forwarded to the real request.

        Returns:
            Any: The real response for every verb but POST.
        """
        if method == "POST":
            raise _TIMEOUT
        return await super()._make_request(method, url, *args, **kwargs)


class _ConnectRefused(GrampsWebAPIClient):
    """Client whose POSTs fail to connect; it records every verb it is asked."""

    def __init__(self):
        """Start with no recorded requests."""
        super().__init__()
        self.methods = []

    async def _make_request(self, method, url, *args, **kwargs):
        """
        Record the verb; fail a POST unsent and send every other request.

        Args:
            method (str): HTTP verb.
            url (str): Request URL.
            *args: Forwarded to the real request.
            **kwargs: Forwarded to the real request.

        Returns:
            Any: The real response for every verb but POST.
        """
        self.methods.append(method)
        if method == "POST":
            raise GrampsAPIError("Cannot connect to Gramps API: refused")
        return await super()._make_request(method, url, *args, **kwargs)


async def _people_named(first_name: str) -> list:
    """
    List the stored people with one exact first name.

    Args:
        first_name (str): First name to match.

    Returns:
        list: The matching people.
    """
    client = GrampsWebAPIClient()
    return await client.make_api_call(
        api_call=ApiCalls.GET_PEOPLE,
        params=BaseGetMultipleParams(gql=f'primary_name.first_name = "{first_name}"'),
        tree_id=get_settings().gramps_tree_id,
    )


def _person(first_name: str) -> dict:
    """
    Build an upsert_person create payload.

    Args:
        first_name (str): The person's first name.

    Returns:
        dict: The payload.
    """
    return {"primary_name": {"first_name": first_name}, "gender": 2}


@pytest.mark.asyncio
async def test_landed_create_reports_success(monkeypatch):
    """A 500 after the commit returns the stored person, not an error."""
    first_name = f"{TEST_PREFIX}Landed106"
    monkeypatch.setattr(upsert_table, "get_client", _CommitThen500)

    result = await UPSERT_HANDLERS["person"](_person(first_name))

    stored = await _people_named(first_name)
    assert (
        result[0].text.startswith("Successfully created person"),
        [p["handle"] for p in stored],
    ) == (True, [extract_handle(result[0].text)])


@pytest.mark.asyncio
async def test_unwritten_create_says_retry_is_safe(monkeypatch):
    """A 500 before the commit says nothing was written, and nothing is."""
    first_name = f"{TEST_PREFIX}Unwritten106"
    monkeypatch.setattr(upsert_table, "get_client", _500BeforeWrite)

    with pytest.raises(McpToolError) as info:
        await UPSERT_HANDLERS["person"](_person(first_name))

    assert (
        "Nothing was written" in str(info.value),
        await _people_named(first_name),
    ) == (True, [])


@pytest.mark.asyncio
async def test_landed_timeout_reports_success(monkeypatch):
    """A read timeout after the commit returns the stored person (#130)."""
    first_name = f"{TEST_PREFIX}Landed130"
    monkeypatch.setattr(upsert_table, "get_client", _CommitThenTimeout)

    result = await UPSERT_HANDLERS["person"](_person(first_name))

    stored = await _people_named(first_name)
    assert (
        result[0].text.startswith("Successfully created person"),
        [p["handle"] for p in stored],
    ) == (True, [extract_handle(result[0].text)])


@pytest.mark.asyncio
async def test_unstored_timeout_says_check_before_retry(monkeypatch):
    """A timeout with no stored record names the handle to check (#130)."""
    first_name = f"{TEST_PREFIX}Unstored130"
    monkeypatch.setattr(upsert_table, "get_client", _TimeoutBeforeWrite)

    with pytest.raises(McpToolError) as info:
        await UPSERT_HANDLERS["person"](_person(first_name))

    assert (
        "the server may still be saving it" in str(info.value),
        await _people_named(first_name),
    ) == (True, [])


@pytest.mark.asyncio
async def test_connect_error_skips_the_check(monkeypatch):
    """A POST that never connected raises as is, with no lookup (#130)."""
    client = _ConnectRefused()
    monkeypatch.setattr(upsert_table, "get_client", lambda: client)

    with pytest.raises(McpToolError) as info:
        await UPSERT_HANDLERS["person"](_person(f"{TEST_PREFIX}Refused130"))

    assert (str(info.value), client.methods) == (
        "Cannot connect to Gramps API: refused",
        ["POST"],
    )
