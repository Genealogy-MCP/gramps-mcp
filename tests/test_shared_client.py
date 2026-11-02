# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Integration test for the session-wide API client (MCP-21, issue #105).

Consecutive tool calls must reuse one open httpx.AsyncClient instead of
tearing the connection down after every call.
"""

import pytest
from mcp_codemode import execute_operation

from src.gramps_mcp.client import get_client
from src.gramps_mcp.operations import OPERATION_REGISTRY

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_tool_calls_share_one_open_http_client():
    """A read and a GQL search run on the same, still-open connection pool."""
    await execute_operation(
        {"operation": "list_tags", "params": {}}, OPERATION_REGISTRY, None
    )
    http = get_client().auth_manager.client

    await execute_operation(
        {
            "operation": "search",
            "params": {"type": "person", "gql": "gramps_id = I0001"},
        },
        OPERATION_REGISTRY,
        None,
    )

    assert get_client().auth_manager.client is http
    assert not http.is_closed
