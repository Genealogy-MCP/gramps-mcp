# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for how configure_http reads GRAMPS_MCP_HOST and GRAMPS_MCP_PORT (#135).

A set-but-empty variable must fall back to the default, the way Compose's
${GRAMPS_MCP_PORT:-8000} mapping and the image healthcheck already do.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from src.gramps_mcp.server import configure_http


def _configure(monkeypatch, host: str | None, port: str | None) -> FastMCP:
    """Set or clear the two variables, then configure a fresh app from them."""
    for name, value in (("GRAMPS_MCP_HOST", host), ("GRAMPS_MCP_PORT", port)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    app = FastMCP("gramps", stateless_http=True, json_response=True)
    configure_http(app)
    return app


@pytest.mark.parametrize(
    ("host", "port", "expected"),
    [
        (None, None, ("127.0.0.1", 8000)),
        ("", "", ("127.0.0.1", 8000)),
        ("0.0.0.0", "8123", ("0.0.0.0", 8123)),
    ],
    ids=["unset", "empty", "set"],
)
def test_host_and_port(monkeypatch, host, port, expected):
    """Unset and empty values both take the defaults; set values win."""
    app = _configure(monkeypatch, host, port)
    assert (app.settings.host, app.settings.port) == expected


def test_non_integer_port_names_the_variable(monkeypatch):
    """A port that is not an integer fails with the variable and an example."""
    with pytest.raises(
        ValueError,
        match=r"GRAMPS_MCP_PORT must be an integer port number such as 8000, got 'abc'",
    ):
        _configure(monkeypatch, None, "abc")
