# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Integration tests for create_backup and list_backups (gramps-webapi 3.24+).

Run against the local Docker test instance only. Its compose file sets a
backup directory and a high backup_keep, so every create here survives the
run; `make test` resets the volumes before the next one.
"""

import re

import pytest
from mcp_codemode import execute_operation

from src.gramps_mcp.auth import AuthManager
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.operations import OPERATION_REGISTRY
from src.gramps_mcp.tools._errors import McpToolError
from tests._test_env import EDITOR_PASSWORD, EDITOR_USERNAME

pytestmark = pytest.mark.integration

_ID = re.compile(r"id: (\S+)")


async def _run(operation: str, params: dict | None = None) -> str:
    """Execute an operation through the registry and return its text."""
    args = {"operation": operation, "params": params or {}}
    result = await execute_operation(args, OPERATION_REGISTRY, None)
    return result[0].text


@pytest.fixture(scope="class")
def as_editor():
    """Log in as the seeded Editor, then hand the Owner's session back.

    Reason: the token endpoint allows one login per second. Re-logging the
    Owner after each test would chain 429s into the tests that follow, so the
    Owner's AuthManager is stashed and restored instead, and one Editor login
    serves every test in the class.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GRAMPS_USERNAME", EDITOR_USERNAME)
        mp.setenv("GRAMPS_PASSWORD", EDITOR_PASSWORD)
        mp.setattr(AuthManager, "_instance", None)
        get_settings.cache_clear()
        yield
    get_settings.cache_clear()


class TestCreateAndList:
    """Happy path: a created backup is listed first."""

    @pytest.mark.asyncio
    async def test_created_backup_is_listed_first(self):
        created = await _run("create_backup")
        assert created.startswith("Backup created.")
        assert "prunes the rest after every create" in created
        backup_id = _ID.search(created).group(1)

        listed = await _run("list_backups")
        assert _ID.search(listed).group(1) == backup_id

    @pytest.mark.asyncio
    async def test_limit_one_returns_one_row_and_truncation(self):
        await _run("create_backup")
        await _run("create_backup")

        listed = await _run("list_backups", {"limit": 1})
        assert "(showing 1)" in listed
        assert len(_ID.findall(listed)) == 1


@pytest.mark.usefixtures("as_editor")
class TestPermission:
    """An Editor lacks ManageBackups and gets the mapped 403 message."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("operation", ["create_backup", "list_backups"])
    async def test_editor_gets_permission_error(self, operation):
        with pytest.raises(McpToolError, match="ManageBackups"):
            await _run(operation)


class TestInvalidInput:
    """Parameter validation rejects the call before any request."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("limit", [0, 201])
    async def test_limit_out_of_range(self, limit):
        with pytest.raises(McpToolError, match="Invalid parameters"):
            await _run("list_backups", {"limit": limit})

    @pytest.mark.asyncio
    async def test_create_rejects_unknown_parameter(self):
        with pytest.raises(McpToolError, match="Invalid parameters"):
            await _run("create_backup", {"tree": "other"})
