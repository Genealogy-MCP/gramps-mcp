# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Route a mocked client's ``call_resource`` through its ``make_api_call``.

The generic upsert (#102, #103) calls ``call_resource(method, path, ...)``
with a resource-table path; the unit tests written against the hand
upserts mock ``make_api_call`` keyed by ``ApiCalls`` member. Every table
path has an ``ApiCalls`` member with the same (verb, path) value, so the
shim maps one onto the other and the existing mocks and assertions keep
working unchanged.
"""

from unittest.mock import AsyncMock

from src.gramps_mcp.models.api_calls import ApiCalls


def route_call_resource(client: AsyncMock) -> AsyncMock:
    """
    Make ``client.call_resource`` delegate to ``client.make_api_call``.

    Args:
        client (AsyncMock): Mocked ``GrampsWebAPIClient`` instance.

    Returns:
        AsyncMock: The same client, for chaining.
    """

    async def call_resource(method, path, params=None, tree_id=None, **url_params):
        """
        Forward one resource call as the matching ``ApiCalls`` member.

        Args:
            method (str): HTTP verb.
            path (str): Path template from the table row.
            params: Parsed params model.
            tree_id (str): Tree id.
            **url_params: Path placeholders (``handle``).

        Returns:
            Any: Whatever the mocked ``make_api_call`` returns.
        """
        return await client.make_api_call(
            api_call=ApiCalls((method, path)),
            params=params,
            tree_id=tree_id,
            handle=url_params.get("handle"),
        )

    client.call_resource = AsyncMock(side_effect=call_resource)
    return client
