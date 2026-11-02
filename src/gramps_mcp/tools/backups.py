# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Backup operations: create_backup and list_backups (gramps-webapi 3.24+).

Thin wrappers over ``POST /api/backups/`` and ``GET /api/backups/``. Restore,
download and delete stay outside the MCP (Gramps Web UI or the raw API).
"""

import json
import logging
from typing import Any, Dict, List

from mcp.types import TextContent
from pydantic import BaseModel, TypeAdapter, ValidationError

from ..client import GrampsAPIError, GrampsWebAPIClient
from ..models.api_calls import ApiCalls
from ..models.parameters.backup_params import CreateBackupParams, ListBackupsParams
from ._errors import McpToolError, describe_backup_error, parse_params, raise_tool_error
from .analysis import _wait_for_task_completion
from .search_basic import with_client

logger = logging.getLogger(__name__)

# Reason: a backup snapshots the whole tree in a worker task, and the task can
# wait in the broker queue before a worker picks it up; large trees take
# minutes, not the seconds a report needs.
BACKUP_TASK_TIMEOUT = 300


class BackupRecord(BaseModel):
    """One stored backup as the 3.24 ``Backup`` schema describes it."""

    model_config = {"extra": "ignore"}

    id: str
    size: int
    restorable: bool
    manifest: Dict[str, Any] = {}

    @property
    def created(self) -> str:
        """Return the manifest's creation timestamp (UTC, ISO 8601)."""
        return str(self.manifest.get("created", "unknown"))


_BACKUP_LIST = TypeAdapter(List[BackupRecord])


def _parse_backups(payload: Any) -> List[BackupRecord]:
    """Parse a backups list response (V-1).

    Args:
        payload: Decoded JSON body of ``GET /api/backups/``.

    Returns:
        List[BackupRecord]: The parsed backups.

    Raises:
        GrampsAPIError: If the body does not match the Backup schema.
    """
    try:
        return _BACKUP_LIST.validate_python(payload)
    except ValidationError as e:
        raise GrampsAPIError(f"Server sent an unexpected backup payload: {e}") from e


def _parse_backup(payload: Any) -> BackupRecord:
    """Parse a single created backup (V-1).

    Args:
        payload: The 201 body, or the 202 task's result object.

    Returns:
        BackupRecord: The parsed backup.

    Raises:
        GrampsAPIError: If the payload does not match the Backup schema.
    """
    return _parse_backups([payload])[0]


async def _server_info(client: GrampsWebAPIClient) -> Dict[str, Any]:
    """Fetch the ``server`` section of the metadata endpoint, best effort.

    Args:
        client: Gramps API client.

    Returns:
        Dict[str, Any]: The section, or an empty dict when it is unavailable.
    """
    try:
        metadata = await client.make_api_call(api_call=ApiCalls.GET_METADATA)
    except GrampsAPIError as e:
        logger.warning(f"Could not read server metadata for backup limits: {e}")
        return {}
    server = metadata.get("server") if isinstance(metadata, dict) else None
    return server if isinstance(server, dict) else {}


async def _call_backups(client: GrampsWebAPIClient, api_call: ApiCalls) -> Any:
    """Call the backups collection, mapping its error statuses (MCP-9).

    Args:
        client: Gramps API client.
        api_call: ``GET_BACKUPS`` or ``POST_BACKUPS``.

    Returns:
        Any: The decoded response body.

    Raises:
        McpToolError: For 403, 404, 409, 429 and 501, with the mapped message.
        GrampsAPIError: For any other failure, unchanged.
    """
    try:
        return await client.make_api_call(api_call=api_call)
    except GrampsAPIError as e:
        rate_limit = None
        if e.status_code == 429:
            server = await _server_info(client)
            if "rate_limit_backup" in server:
                rate_limit = json.dumps(server["rate_limit_backup"])
        message = describe_backup_error(e, rate_limit)
        if message is None:
            raise
        raise McpToolError(message) from e


async def _created_backup(client: GrampsWebAPIClient, body: Any) -> BackupRecord:
    """Resolve a create response to the backup it made.

    A body holding the backup means 201 (no task queue). A body holding a
    task reference means 202: the task's result object is the backup.

    Args:
        client: Gramps API client.
        body: Decoded body of ``POST /api/backups/``.

    Returns:
        BackupRecord: The new backup.

    Raises:
        GrampsAPIError: If the body is neither shape, or the task fails.
    """
    if isinstance(body, dict) and "id" in body:
        return _parse_backup(body)
    task = body.get("task") if isinstance(body, dict) else None
    if not isinstance(task, dict) or "id" not in task:
        raise GrampsAPIError(
            "Server answered the backup request with neither a backup nor a task."
        )
    result = await _wait_for_task_completion(
        client, task["id"], "", timeout=BACKUP_TASK_TIMEOUT
    )
    return _parse_backup(result)


def _prune_warning(backup_keep: Any) -> str:
    """Build the server-side pruning warning for create_backup output.

    Args:
        backup_keep: ``backup_keep`` from the metadata endpoint, if reported.

    Returns:
        str: The warning sentence.
    """
    kept = (
        f"only the newest {backup_keep} backups"
        if isinstance(backup_keep, int)
        else "only a fixed number of the newest backups"
    )
    return (
        f"The server keeps {kept} per tree and prunes the rest after every "
        "create, so an earlier restore point may already be gone."
    )


@with_client
async def create_backup_tool(client, arguments: Dict) -> List[TextContent]:
    """
    Create a stored backup of the tree and wait until it exists.

    Args:
        client (GrampsWebAPIClient): Injected by ``with_client``.
        arguments (Dict): Operation parameters (none accepted).

    Returns:
        List[TextContent]: The new backup's id and creation timestamp.
    """
    parse_params(CreateBackupParams, arguments)
    try:
        body = await _call_backups(client, ApiCalls.POST_BACKUPS)
        backup = await _created_backup(client, body)
        server = await _server_info(client)
        text = (
            "Backup created.\n\n"
            f"id: {backup.id}\n"
            f"created: {backup.created}\n\n"
            f"{_prune_warning(server.get('backup_keep'))}"
        )
        return [TextContent(type="text", text=text)]
    except Exception as e:
        raise_tool_error(e, "backup creation")


def _format_backup_rows(backups: List[BackupRecord], limit: int) -> str:
    """Format backups newest first, sliced to ``limit``.

    Args:
        backups: Every backup the server listed.
        limit: Maximum number of rows to show.

    Returns:
        str: Header with a truncation note when rows were cut, then one row
            per backup.
    """
    if not backups:
        return "No backups found for this tree. Use create_backup to make one."
    # Reason: the API has no pagination; sort client side so the slice is
    # the newest backups, ties on the second-resolution timestamp by id.
    # Undated backups sort last: "unknown" would otherwise outrank any
    # ISO timestamp.
    ordered = sorted(
        backups,
        key=lambda b: ("created" in b.manifest, b.created, b.id),
        reverse=True,
    )
    shown = ordered[:limit]
    total = len(ordered)
    header = (
        f"Found {total} backups (showing {len(shown)}):\n\n"
        if total > len(shown)
        else f"Found {total} backups:\n\n"
    )
    rows = "".join(
        f"- id: {b.id} | size: {b.size} bytes | "
        f"restorable: {'yes' if b.restorable else 'no'} | created: {b.created}\n"
        for b in shown
    )
    return header + rows


@with_client
async def list_backups_tool(client, arguments: Dict) -> List[TextContent]:
    """
    List the tree's stored backups, newest first.

    Args:
        client (GrampsWebAPIClient): Injected by ``with_client``.
        arguments (Dict): Operation parameters (``limit``).

    Returns:
        List[TextContent]: One row per backup with id, size, restorable flag
            and creation timestamp.
    """
    params = parse_params(ListBackupsParams, arguments)
    try:
        backups = _parse_backups(await _call_backups(client, ApiCalls.GET_BACKUPS))
        text = _format_backup_rows(backups, params.limit)
        return [TextContent(type="text", text=text)]
    except Exception as e:
        raise_tool_error(e, "backup listing")
