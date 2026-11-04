# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for how configure_http reads GRAMPS_MCP_PORT (#135).

A set-but-empty port must fall back to 8000, the way Compose's
${GRAMPS_MCP_PORT:-8000} mapping and the image healthcheck already do.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from src.gramps_mcp.server import configure_http


def _configured_port(monkeypatch, port: str | None) -> int:
    """Set or clear GRAMPS_MCP_PORT, configure a fresh app, return its port."""
    if port is None:
        monkeypatch.delenv("GRAMPS_MCP_PORT", raising=False)
    else:
        monkeypatch.setenv("GRAMPS_MCP_PORT", port)
    app = FastMCP("gramps", stateless_http=True, json_response=True)
    configure_http(app)
    return app.settings.port


@pytest.mark.parametrize(
    ("port", "expected"),
    [(None, 8000), ("", 8000), ("8123", 8123)],
    ids=["unset", "empty", "set"],
)
def test_port(monkeypatch, port, expected):
    """Unset and empty values both take the default; a set value wins."""
    assert _configured_port(monkeypatch, port) == expected


def test_non_integer_port_names_the_variable(monkeypatch):
    """A port that is not an integer fails with the variable and an example."""
    with pytest.raises(
        ValueError,
        match=r"GRAMPS_MCP_PORT must be an integer port number such as 8000, got 'abc'",
    ):
        _configured_port(monkeypatch, "abc")
