# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the /mcp Host header allow-list (issue #127).

Each test builds a fresh FastMCP app, because an app's session manager runs
only once, and posts an MCP initialize request through Starlette's TestClient.
The initialize handshake never calls the Gramps API, so no Docker is needed.
"""

import pytest
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

from src.gramps_mcp.server import configure_http, transport_security

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


def _post_initialize(app: FastMCP, host: str) -> int:
    """POST an initialize request with the given Host header, return the status."""
    with TestClient(app.streamable_http_app()) as client:
        response = client.post(
            "/mcp",
            json=_INITIALIZE,
            headers={"Host": host, "Accept": "application/json, text/event-stream"},
        )
    return response.status_code


def _configured_app(monkeypatch, allowed_hosts: str | None) -> FastMCP:
    """Build an app the way server.py does, then configure it from the env.

    Reason: the bug lived between construction and configure_http, so the
    tests go through both instead of passing transport_security directly.
    """
    if allowed_hosts is None:
        monkeypatch.delenv("GRAMPS_MCP_ALLOWED_HOSTS", raising=False)
    else:
        monkeypatch.setenv("GRAMPS_MCP_ALLOWED_HOSTS", allowed_hosts)
    monkeypatch.setenv("GRAMPS_MCP_HOST", "0.0.0.0")
    app = FastMCP("gramps", stateless_http=True, json_response=True)
    configure_http(app)
    return app


def test_localhost_accepted_by_default(monkeypatch):
    assert _post_initialize(_configured_app(monkeypatch, None), "localhost:8000") == 200


def test_foreign_host_rejected_by_default(monkeypatch):
    assert (
        _post_initialize(_configured_app(monkeypatch, None), "gramps-mcp:8000") == 421
    )


def test_allow_listed_host_accepted(monkeypatch):
    assert (
        _post_initialize(
            _configured_app(monkeypatch, "gramps-mcp:8000, mcp.example.com"),
            "gramps-mcp:8000",
        )
        == 200
    )


def test_allow_listed_port_wildcard_accepted(monkeypatch):
    assert (
        _post_initialize(
            _configured_app(monkeypatch, "gramps-mcp:*"), "gramps-mcp:9000"
        )
        == 200
    )


def test_host_outside_allow_list_still_rejected(monkeypatch):
    assert (
        _post_initialize(
            _configured_app(monkeypatch, "mcp.example.com"), "evil.example.com"
        )
        == 421
    )


def test_allow_list_extends_localhost_defaults():
    assert transport_security("mcp.example.com,,").allowed_hosts == [
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
        "mcp.example.com",
    ]


@pytest.mark.parametrize("entry", ["https://mcp.example.com", "mcp.example.com/mcp"])
def test_url_shaped_entry_rejected(entry):
    with pytest.raises(ValueError, match="GRAMPS_MCP_ALLOWED_HOSTS"):
        transport_security(entry)
