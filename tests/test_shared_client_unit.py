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


@pytest.mark.asyncio
async def test_lifespan_leaves_the_shared_client_open():
    """Stateless HTTP enters the lifespan per request, so it must not close."""
    from src.gramps_mcp.server import server_lifespan

    shared = AsyncMock()
    with (
        patch("src.gramps_mcp.server.verify_api_on_startup", new_callable=AsyncMock),
        patch("src.gramps_mcp.server.get_client", return_value=shared),
    ):
        async with server_lifespan(None):
            pass
        async with server_lifespan(None):
            pass

    shared.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_server_closes_the_shared_client_on_exit():
    """The HTTP runner closes the shared client once, after the server stops."""
    from src.gramps_mcp import server

    shared = AsyncMock()
    with (
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
