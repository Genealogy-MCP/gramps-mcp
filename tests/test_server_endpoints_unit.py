# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the server root and health HTTP endpoints.

Covers version derivation from the package (no stale hardcoding) and
meta-tool count derivation from the FastMCP registration (MCP-6), by
calling the async route handlers directly -- they ignore their request
argument, so no running server is required.
"""

import json
import re
from pathlib import Path

import src.gramps_mcp.server as srv
from src.gramps_mcp import __version__
from src.gramps_mcp.server import app, health_check, root


def _pyproject_version() -> str:
    """Read [project].version from pyproject.toml.

    Uses a regex rather than tomllib so the test runs on Python 3.10
    (tomllib is stdlib only from 3.11), mirroring scripts/version_check.py.
    """
    text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


async def _json(handler) -> dict:
    """Call an async route handler with no request and parse its JSON body."""
    response = await handler(None)
    return json.loads(response.body)


async def test_root_reports_package_version():
    data = await _json(root)
    assert data["version"] == __version__
    assert data["version"] != "2.0.0"


def test_package_version_matches_pyproject():
    assert __version__ == _pyproject_version()


async def test_root_tools_count_derived_from_registration():
    data = await _json(root)
    assert data["tools_count"] == len(await app.list_tools())


async def test_health_tools_count_derived_from_registration():
    data = await _json(health_check)
    assert data["tools"] == len(await app.list_tools())


def test_meta_tool_count_constant_removed():
    assert not hasattr(srv, "_META_TOOL_COUNT")
