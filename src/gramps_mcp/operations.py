# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Operation registry for Code Mode architecture (MCP-29 through MCP-34).

Assembles every available operation: handwritten entries here plus the
entries ``registry_build`` builds from the generated resource table and
the overlays in ``overlays.py`` and ``write_overlays.py``. Each entry describes
an operation's name, category, parameter schema, handler function, and
behavioral hints. The ``search`` meta-tool queries this registry; the
``execute`` meta-tool dispatches to the handler.

OperationEntry, search_operations, and summarize_params are provided by
the shared mcp-codemode library.
"""

from mcp_codemode import OperationEntry

from .models.parameters.analysis_params import (
    AncestorsParams,
    DescendantsParams,
    TreeInfoParams,
)
from .models.parameters.backup_params import CreateBackupParams, ListBackupsParams
from .models.parameters.media_params import MediaDownloadParams
from .models.parameters.simple_params import SimpleSearchParams
from .models.parameters.transactions_params import TransactionHistoryParams
from .overlays import table_overlays
from .registry_build import build_registry, merge_registry
from .resource_table import ENTITY_RESOURCES

# Import handlers directly from sub-modules (not tools/__init__.py)
# to avoid circular imports — server.py imports from this module.
from .tools.analysis import (
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
)
from .tools.backups import create_backup_tool, list_backups_tool
from .tools.data_management_media import download_media_tool
from .tools.search_basic import search_text_tool
from .write_overlays import upsert_overlays

# Server prerequisites and archive contents, shared by both backup entries.
_BACKUP_NOTES = (
    "Requires gramps-webapi 3.24 or newer, a backup directory configured on "
    "the server (BACKUP_DIR), and an account with the Owner role or above. "
    "An archive holds the tree, the tree settings and the user list without "
    "credentials, but no media files. Restore, download and delete are not "
    "exposed; use the Gramps Web UI."
)

# ---------------------------------------------------------------------------
# Handwritten operations. search, list_tags, get and delete (#101) and the
# ten upserts (#102, #103) are built from the resource table
# (TABLE_OPERATIONS and UPSERT_OPERATIONS below).
# ---------------------------------------------------------------------------

_HANDWRITTEN: dict[str, OperationEntry] = {
    # --- search ---
    "search_text": OperationEntry(
        name="search_text",
        summary="Full-text search across all record types",
        description=(
            "Text search across all record types - matches literal text "
            "within records, not logical combinations"
        ),
        category="search",
        params_schema=SimpleSearchParams,
        handler=search_text_tool,
        read_only=True,
        destructive=False,
    ),
    # --- read ---
    "get_tree_stats": OperationEntry(
        name="get_tree_stats",
        summary="Get tree statistics (counts of people, families, events, etc.)",
        description=(
            "Get information about a specific tree including statistics "
            "(counts of people, families, events, etc.)"
        ),
        category="read",
        params_schema=TreeInfoParams,
        handler=get_tree_stats_tool,
        read_only=True,
        destructive=False,
    ),
    "download_media": OperationEntry(
        name="download_media",
        summary="Download a media file from Gramps Web to local disk",
        description=(
            "Download a media file (photo, document, etc.) from Gramps Web to a "
            "local file path. Provide either the media handle or gramps_id, plus "
            "an absolute destination path. The parent directory must exist."
        ),
        category="read",
        params_schema=MediaDownloadParams,
        handler=download_media_tool,
        read_only=True,
        destructive=False,
    ),
    "list_backups": OperationEntry(
        name="list_backups",
        summary="List the tree's stored server-side backups, newest first",
        description=(
            "List the stored backups (restore points) of the tree, newest "
            "first. Use it to find the most recent backup before or after a "
            "run of writes. Returns one row per backup with id, size in "
            "bytes, whether this server can restore it, and its creation "
            "timestamp (UTC). Returns at most `limit` rows (default 20, "
            "maximum 200) and says when rows were cut. " + _BACKUP_NOTES
        ),
        category="read",
        params_schema=ListBackupsParams,
        handler=list_backups_tool,
        read_only=True,
        destructive=False,
    ),
    # --- write (every upsert is table-built; create_backup stays here) ---
    "create_backup": OperationEntry(
        name="create_backup",
        summary="Create a server-side backup (restore point) of the tree",
        description=(
            "Create a stored backup of the whole tree on the server and wait "
            "until it exists (up to 300 seconds). The server runs one backup "
            "per tree at a time and refuses a second while one runs. Use it "
            "before a batch of writes so a bad batch can be rolled back. "
            "Returns the new backup's id and creation timestamp. WARNING: "
            "the server keeps only the newest backup_keep backups per tree "
            "(a server setting, quoted in the result) and deletes the oldest "
            "after every create, so an earlier restore point, including one "
            "another agent made, may not survive. Backups are rate limited "
            "per tree. " + _BACKUP_NOTES
        ),
        category="write",
        params_schema=CreateBackupParams,
        handler=create_backup_tool,
        read_only=False,
        destructive=False,
    ),
    # --- analysis (3) ---
    "get_ancestors": OperationEntry(
        name="get_ancestors",
        summary="Find all ancestors of a person",
        description=(
            "Find all ancestors of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        category="analysis",
        params_schema=AncestorsParams,
        handler=get_ancestors_tool,
        read_only=True,
        destructive=False,
        token_warning="Very token-heavy. Use max_generations <= 5 to limit output.",
    ),
    "get_descendants": OperationEntry(
        name="get_descendants",
        summary="Find all descendants of a person",
        description=(
            "Find all descendants of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        category="analysis",
        params_schema=DescendantsParams,
        handler=get_descendants_tool,
        read_only=True,
        destructive=False,
        token_warning="Very token-heavy. Use max_generations <= 5 to limit output.",
    ),
    "get_recent_changes": OperationEntry(
        name="get_recent_changes",
        summary="Get recent changes/modifications to the family tree",
        description=(
            "Get recent changes/modifications to the family tree, newest first. "
            "Returns one page of transactions, 20 by default and at most 100, "
            "naming up to 3 changed objects each. Use page for older changes "
            "and keep pagesize the same between pages."
        ),
        category="analysis",
        params_schema=TransactionHistoryParams,
        handler=get_recent_changes_tool,
        read_only=True,
        destructive=False,
    ),
}

TABLE_OPERATIONS: dict[str, OperationEntry] = build_registry(
    ENTITY_RESOURCES, table_overlays()
)

UPSERT_OPERATIONS: dict[str, OperationEntry] = build_registry(
    ENTITY_RESOURCES, upsert_overlays()
)

# Listing order of the search meta-tool (empty query lists in this order).
_OPERATION_ORDER = (
    "search",
    "search_text",
    "list_tags",
    "get",
    "get_tree_stats",
    "download_media",
    "list_backups",
    "upsert_person",
    "upsert_family",
    "upsert_event",
    "upsert_place",
    "upsert_source",
    "upsert_citation",
    "upsert_note",
    "upsert_media",
    "upsert_repository",
    "upsert_tag",
    "create_backup",
    "delete",
    "get_ancestors",
    "get_descendants",
    "get_recent_changes",
)

# ---------------------------------------------------------------------------
# OPERATION_REGISTRY: handwritten plus table-driven operations
# ---------------------------------------------------------------------------

OPERATION_REGISTRY: dict[str, OperationEntry] = merge_registry(
    _HANDWRITTEN, {**TABLE_OPERATIONS, **UPSERT_OPERATIONS}, _OPERATION_ORDER
)
