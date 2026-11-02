# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the create_backup and list_backups operations (#110).

Output shaping from canned API payloads (201 body, 202 plus task result,
list body), error mapping on GrampsAPIError.status_code, and the limit
bounds. GrampsWebAPIClient is mocked; no network.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp_codemode import execute_operation, search_operations
from pydantic import ValidationError

from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.models.parameters.backup_params import ListBackupsParams
from src.gramps_mcp.operations import OPERATION_REGISTRY
from src.gramps_mcp.tools._errors import McpToolError, describe_backup_error
from src.gramps_mcp.tools.backups import (
    BACKUP_TASK_TIMEOUT,
    create_backup_tool,
    list_backups_tool,
)

_CLIENT = "src.gramps_mcp.tools.search_basic.GrampsWebAPIClient"
_WAIT = "src.gramps_mcp.tools.backups._wait_for_task_completion"


def _backup(backup_id: str, created: str, size: int = 2048) -> dict:
    """Build a backup record shaped like the 3.24 Backup schema."""
    return {
        "id": backup_id,
        "size": size,
        "restorable": True,
        "manifest": {"created": created, "tree": "t1"},
    }


def _client(responses: dict) -> MagicMock:
    """Build a mocked client answering make_api_call by ApiCalls name.

    A value that is an exception is raised instead of returned.
    """
    client = MagicMock()
    client.base_url = "http://test/api"
    client.close = AsyncMock()

    async def make_api_call(api_call, params=None, tree_id=None, **kw):
        value = responses[api_call.name]
        if isinstance(value, Exception):
            raise value
        return value

    client.make_api_call = AsyncMock(side_effect=make_api_call)
    return client


class TestCreateBackupShaping:
    """create_backup output from 201 and 202 responses."""

    @pytest.mark.asyncio
    async def test_201_body_returns_id_created_and_keep(self):
        client = _client(
            {
                "POST_BACKUPS": _backup("b-201", "2026-11-02T10:00:00Z"),
                "GET_METADATA": {"server": {"backup_keep": 5}},
            }
        )
        with patch(_CLIENT, return_value=client):
            result = await create_backup_tool({})

        assert result[0].text == (
            "Backup created.\n\n"
            "id: b-201\n"
            "created: 2026-11-02T10:00:00Z\n\n"
            "The server keeps only the newest 5 backups per tree and prunes "
            "the rest after every create, so an earlier restore point may "
            "already be gone."
        )

    @pytest.mark.asyncio
    async def test_202_task_result_is_polled_with_300s_timeout(self):
        client = _client(
            {
                "POST_BACKUPS": {"task": {"id": "task-1", "href": "/api/tasks/x"}},
                "GET_METADATA": {"server": {"backup_keep": 1000}},
            }
        )
        wait = AsyncMock(return_value=_backup("b-202", "2026-11-02T11:00:00Z"))
        with patch(_CLIENT, return_value=client), patch(_WAIT, wait):
            result = await create_backup_tool({})

        wait.assert_awaited_once_with(client, "task-1", "", timeout=BACKUP_TASK_TIMEOUT)
        assert BACKUP_TASK_TIMEOUT == 300
        assert "id: b-202\ncreated: 2026-11-02T11:00:00Z" in result[0].text
        assert "newest 1000 backups" in result[0].text

    @pytest.mark.asyncio
    async def test_keep_absent_from_metadata_still_warns(self):
        client = _client(
            {
                "POST_BACKUPS": _backup("b1", "2026-11-02T10:00:00Z"),
                "GET_METADATA": {"server": {}},
            }
        )
        with patch(_CLIENT, return_value=client):
            result = await create_backup_tool({})

        assert "keeps only a fixed number of the newest backups" in result[0].text

    @pytest.mark.asyncio
    async def test_metadata_failure_does_not_fail_the_create(self, caplog):
        client = _client(
            {
                "POST_BACKUPS": _backup("b1", "2026-11-02T10:00:00Z"),
                "GET_METADATA": GrampsAPIError("boom", status_code=500),
            }
        )
        with patch(_CLIENT, return_value=client):
            result = await create_backup_tool({})

        assert "id: b1" in result[0].text
        assert "metadata" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_task_result_without_id_is_a_tool_error(self):
        client = _client({"POST_BACKUPS": {"task": {"id": "task-1"}}})
        wait = AsyncMock(return_value={"state": "SUCCESS"})
        with patch(_CLIENT, return_value=client), patch(_WAIT, wait):
            with pytest.raises(McpToolError, match="unexpected backup payload"):
                await create_backup_tool({})

    @pytest.mark.asyncio
    async def test_body_without_id_or_task_is_a_tool_error(self):
        client = _client({"POST_BACKUPS": {"unexpected": True}})
        with patch(_CLIENT, return_value=client):
            with pytest.raises(McpToolError, match="neither a backup nor a task"):
                await create_backup_tool({})

    @pytest.mark.asyncio
    async def test_unknown_parameter_rejected(self):
        with pytest.raises(McpToolError, match="Unknown parameter"):
            await create_backup_tool({"name": "nightly"})


class TestListBackupsShaping:
    """list_backups ordering, slicing and truncation note."""

    _UNSORTED = [
        _backup("aaa", "2026-11-01T09:00:00Z", size=100),
        _backup("ccc", "2026-11-02T09:00:00Z", size=300),
        _backup("bbb", "2026-11-02T09:00:00Z", size=200),
    ]

    @pytest.mark.asyncio
    async def test_rows_newest_first_with_id_tiebreak(self):
        client = _client({"GET_BACKUPS": self._UNSORTED})
        with patch(_CLIENT, return_value=client):
            result = await list_backups_tool({})

        assert result[0].text == (
            "Found 3 backups:\n\n"
            "- id: ccc | size: 300 bytes | restorable: yes | "
            "created: 2026-11-02T09:00:00Z\n"
            "- id: bbb | size: 200 bytes | restorable: yes | "
            "created: 2026-11-02T09:00:00Z\n"
            "- id: aaa | size: 100 bytes | restorable: yes | "
            "created: 2026-11-01T09:00:00Z\n"
        )

    @pytest.mark.asyncio
    async def test_limit_slices_and_reports_truncation(self):
        client = _client({"GET_BACKUPS": self._UNSORTED})
        with patch(_CLIENT, return_value=client):
            result = await list_backups_tool({"limit": 1})

        assert result[0].text == (
            "Found 3 backups (showing 1):\n\n"
            "- id: ccc | size: 300 bytes | restorable: yes | "
            "created: 2026-11-02T09:00:00Z\n"
        )

    @pytest.mark.asyncio
    async def test_unrestorable_backup_is_flagged(self):
        record = {**_backup("old", "2025-01-01T00:00:00Z"), "restorable": False}
        client = _client({"GET_BACKUPS": [record]})
        with patch(_CLIENT, return_value=client):
            result = await list_backups_tool({})

        assert "restorable: no" in result[0].text

    @pytest.mark.asyncio
    async def test_empty_list(self):
        client = _client({"GET_BACKUPS": []})
        with patch(_CLIENT, return_value=client):
            result = await list_backups_tool({})

        assert result[0].text == (
            "No backups found for this tree. Use create_backup to make one."
        )

    @pytest.mark.asyncio
    async def test_malformed_list_is_a_tool_error(self):
        client = _client({"GET_BACKUPS": [{"id": "x"}]})
        with patch(_CLIENT, return_value=client):
            with pytest.raises(McpToolError, match="unexpected backup payload"):
                await list_backups_tool({})


class TestLimitBounds:
    """limit must stay inside 1..200."""

    @pytest.mark.parametrize("limit", [0, -1, 201])
    def test_out_of_range_rejected_by_model(self, limit):
        with pytest.raises(ValidationError):
            ListBackupsParams(limit=limit)

    @pytest.mark.parametrize("limit", [1, 200])
    def test_bounds_accepted(self, limit):
        assert ListBackupsParams(limit=limit).limit == limit

    def test_default_is_20(self):
        assert ListBackupsParams().limit == 20

    @pytest.mark.asyncio
    @pytest.mark.parametrize("limit", [0, 201])
    async def test_out_of_range_rejected_through_execute(self, limit):
        with pytest.raises(McpToolError, match="Invalid parameters"):
            await execute_operation(
                {"operation": "list_backups", "params": {"limit": limit}},
                OPERATION_REGISTRY,
                None,
            )


class TestDescribeBackupError:
    """Status-code mapping in the shared error module."""

    def test_status_messages(self):
        messages = {
            code: describe_backup_error(GrampsAPIError("x", status_code=code))
            for code in (501, 403, 404, 500)
        }
        assert messages == {
            501: (
                "Server has no backup directory configured (BACKUP_DIR); "
                "ask the server administrator to set one."
            ),
            403: (
                "Account lacks the ManageBackups permission; the Owner role "
                "or above is required."
            ),
            404: (
                "Server is older than gramps-webapi 3.24 and has no backup endpoints."
            ),
            500: None,
        }

    def test_429_echoes_rate_limit(self):
        error = GrampsAPIError("x", status_code=429)
        assert describe_backup_error(error, '[{"amount": 10}]') == (
            "Backup rate limit for this tree reached; the server allows "
            '[{"amount": 10}]. Wait for the window to pass before retrying.'
        )

    def test_429_without_reported_limit(self):
        error = GrampsAPIError("x", status_code=429)
        assert "the server did not report its limit" in str(
            describe_backup_error(error)
        )

    def test_no_status_code(self):
        assert describe_backup_error(GrampsAPIError("timeout")) is None


class TestHandlerErrorMapping:
    """Both handlers return the mapped message as a tool error."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("code", "fragment"),
        [
            (501, "BACKUP_DIR"),
            (403, "ManageBackups"),
            (404, "older than gramps-webapi 3.24"),
        ],
    )
    @pytest.mark.parametrize(
        ("tool", "call"),
        [(create_backup_tool, "POST_BACKUPS"), (list_backups_tool, "GET_BACKUPS")],
    )
    async def test_status_mapped(self, tool, call, code, fragment):
        client = _client({call: GrampsAPIError("raw", status_code=code)})
        with patch(_CLIENT, return_value=client):
            with pytest.raises(McpToolError, match=fragment):
                await tool({})

    @pytest.mark.asyncio
    async def test_429_quotes_metadata_rate_limit(self):
        limit = [{"amount": 1000, "window_seconds": 3600}]
        client = _client(
            {
                "POST_BACKUPS": GrampsAPIError("raw", status_code=429),
                "GET_METADATA": {"server": {"rate_limit_backup": limit}},
            }
        )
        with patch(_CLIENT, return_value=client):
            with pytest.raises(McpToolError) as excinfo:
                await create_backup_tool({})

        assert str(excinfo.value) == (
            "Backup rate limit for this tree reached; the server allows "
            '[{"amount": 1000, "window_seconds": 3600}]. Wait for the window '
            "to pass before retrying."
        )

    @pytest.mark.asyncio
    async def test_429_when_metadata_omits_rate_limit(self):
        client = _client(
            {
                "GET_BACKUPS": GrampsAPIError("raw", status_code=429),
                "GET_METADATA": {"server": {"backups": True}},
            }
        )
        with patch(_CLIENT, return_value=client):
            with pytest.raises(McpToolError, match="did not report its limit"):
                await list_backups_tool({})

    @pytest.mark.asyncio
    async def test_unmapped_status_keeps_client_message(self):
        client = _client(
            {"GET_BACKUPS": GrampsAPIError("Server error (500)", status_code=500)}
        )
        with patch(_CLIENT, return_value=client):
            with pytest.raises(McpToolError, match=r"Server error \(500\)"):
                await list_backups_tool({})


class TestRegistryEntries:
    """Discovery and behavioral flags."""

    def test_search_backup_returns_both(self):
        names = {
            entry.name for entry in search_operations("backup", OPERATION_REGISTRY)
        }
        assert {"create_backup", "list_backups"} <= names

    def test_flags_and_categories(self):
        entries = {
            name: (
                OPERATION_REGISTRY[name].category,
                OPERATION_REGISTRY[name].read_only,
                OPERATION_REGISTRY[name].destructive,
            )
            for name in ("create_backup", "list_backups")
        }
        assert entries == {
            "create_backup": ("write", False, False),
            "list_backups": ("read", True, False),
        }
