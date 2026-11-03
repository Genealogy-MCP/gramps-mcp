# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the session-wide API client (MCP-21, issue #105).

Tool handlers share one GrampsWebAPIClient from get_client(); only the
transport runner closes it, once, when the process stops.
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.auth import AuthManager
from src.gramps_mcp.client import GrampsWebAPIClient, get_client
from src.gramps_mcp.tools.search_basic import with_client

_SRC = Path(__file__).resolve().parent.parent / "src" / "gramps_mcp"


def _constructor_calls(path: Path) -> list[int]:
    """Return the line numbers of every GrampsWebAPIClient() call in path."""
    tree = ast.parse(path.read_text(), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "GrampsWebAPIClient"
    ]


def test_get_client_returns_one_instance():
    """Every caller in the session gets the same client."""
    assert get_client() is get_client()
    assert isinstance(get_client(), GrampsWebAPIClient)


def test_get_client_follows_a_replaced_auth_manager(monkeypatch):
    """A new AuthManager singleton (another user's login) gets a new client."""
    first = get_client()
    monkeypatch.setattr(AuthManager, "_instance", None)
    second = get_client()
    assert (second is first, second.auth_manager is AuthManager()) == (False, True)


def test_no_tool_handler_constructs_a_client():
    """Handlers and startup take the shared client instead of building one."""
    paths = [*sorted((_SRC / "tools").glob("*.py")), _SRC / "startup.py"]
    offenders = {
        str(path.relative_to(_SRC)): lines
        for path in paths
        if (lines := _constructor_calls(path))
    }
    assert offenders == {}


@pytest.mark.asyncio
async def test_with_client_keeps_the_shared_client_open():
    """with_client injects the shared client and never closes it."""
    shared = AsyncMock()
    seen = []

    @with_client
    async def handler(client, arguments):
        seen.append(client)

    with patch("src.gramps_mcp.tools.search_basic.get_client", return_value=shared):
        await handler({})
        await handler({})

    assert seen == [shared, shared]
    shared.close.assert_not_awaited()


def _call_search_over_http() -> None:
    """POST one stateless tools/call for the local search meta-tool."""
    from starlette.testclient import TestClient

    from src.gramps_mcp import server

    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "search", "arguments": {"arguments": {"query": "tag"}}},
    }
    headers = {"Accept": "application/json, text/event-stream"}
    # Reason: a fresh session manager per app, because one can run only once.
    server.app._session_manager = None
    with TestClient(
        server.app.streamable_http_app(), base_url="http://localhost:8000"
    ) as http:
        response = http.post("/mcp", json=call, headers=headers)
    assert response.status_code == 200, response.text


def test_http_tool_call_skips_version_check_and_keeps_client_open():
    """Stateless HTTP enters the lifespan per request (#121, MCP-21).

    So a tool call must not repeat the startup metadata/ check or close
    the shared client.
    """
    shared = AsyncMock()
    with (
        patch(
            "src.gramps_mcp.server.verify_api_on_startup", new_callable=AsyncMock
        ) as verify,
        patch("src.gramps_mcp.server.get_client", return_value=shared),
    ):
        _call_search_over_http()
        _call_search_over_http()

    verify.assert_not_awaited()
    shared.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_server_verifies_the_api_once_at_start():
    """The HTTP runner checks the API version once, before serving."""
    from src.gramps_mcp import server

    order = []
    with (
        patch(
            "src.gramps_mcp.server.verify_api_on_startup",
            new_callable=AsyncMock,
            side_effect=lambda: order.append("verify"),
        ),
        patch.object(
            server.app,
            "run_streamable_http_async",
            new_callable=AsyncMock,
            side_effect=lambda: order.append("serve"),
        ),
        patch("src.gramps_mcp.server.get_client", return_value=AsyncMock()),
    ):
        await server.run_http_server()

    assert order == ["verify", "serve"]


@pytest.mark.asyncio
async def test_http_server_closes_the_shared_client_on_exit():
    """The HTTP runner closes the shared client once, after the server stops."""
    from src.gramps_mcp import server

    shared = AsyncMock()
    with (
        patch("src.gramps_mcp.server.verify_api_on_startup", new_callable=AsyncMock),
        patch.object(server.app, "run_streamable_http_async", new_callable=AsyncMock),
        patch("src.gramps_mcp.server.get_client", return_value=shared),
    ):
        await server.run_http_server()

    shared.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_stdio_server_closes_the_shared_client_on_exit():
    """The stdio runner closes the shared client even when the transport fails."""
    from src.gramps_mcp import server

    shared = AsyncMock()
    with (
        patch("src.gramps_mcp.server.verify_api_on_startup", new_callable=AsyncMock),
        patch("src.gramps_mcp.server.stdio_server", side_effect=RuntimeError("eof")),
        patch("src.gramps_mcp.server.get_client", return_value=shared),
        pytest.raises(RuntimeError, match="eof"),
    ):
        await server.run_stdio_server()

    shared.close.assert_awaited_once()
