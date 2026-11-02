# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Operation registry for Code Mode architecture (MCP-29 through MCP-34).

Single source of truth for all available operations. Each entry describes
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
from .models.parameters.citation_params import CitationData
from .models.parameters.event_params import EventSaveParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaDownloadParams, MediaSaveParams
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.simple_params import SimpleSearchParams
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.tag_params import TagSaveParams
from .models.parameters.transactions_params import TransactionHistoryParams
from .operation_overlays import TABLE_OVERLAYS
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
from .tools.data_management import (
    upsert_citation_tool,
    upsert_event_tool,
    upsert_family_tool,
    upsert_note_tool,
    upsert_person_tool,
    upsert_place_tool,
    upsert_repository_tool,
    upsert_source_tool,
)
from .tools.data_management_delete import upsert_tag_tool
from .tools.data_management_media import download_media_tool, upsert_media_tool
from .tools.search_basic import search_text_tool

# Server prerequisites and archive contents, shared by both backup entries.
_BACKUP_NOTES = (
    "Requires gramps-webapi 3.24 or newer, a backup directory configured on "
    "the server (BACKUP_DIR), and an account with the Owner role or above. "
    "An archive holds the tree, the tree settings and the user list without "
    "credentials, but no media files. Restore, download and delete are not "
    "exposed; use the Gramps Web UI."
)

# ---------------------------------------------------------------------------
# Handwritten operations. search, list_tags, get and delete are built from
# the resource table (TABLE_OPERATIONS below, #101).
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
    # --- write (11) ---
    "upsert_person": OperationEntry(
        name="upsert_person",
        summary="Create or update a person record",
        description=(
            "Create or update person information including family links, "
            "event associations, and alternate names (AKA, married names)"
        ),
        category="write",
        params_schema=PersonData,
        handler=upsert_person_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_family": OperationEntry(
        name="upsert_family",
        summary="Create or update a family unit",
        description="Create or update family unit including member relationships",
        category="write",
        params_schema=FamilySaveParams,
        handler=upsert_family_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_event": OperationEntry(
        name="upsert_event",
        summary="Create or update a life event",
        description=("Create or update life event including person/place associations"),
        category="write",
        params_schema=EventSaveParams,
        handler=upsert_event_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_place": OperationEntry(
        name="upsert_place",
        summary="Create or update a geographic location",
        description="Create or update geographic location",
        category="write",
        params_schema=PlaceSaveParams,
        handler=upsert_place_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_source": OperationEntry(
        name="upsert_source",
        summary="Create or update a source document",
        description="Create or update source document",
        category="write",
        params_schema=SourceSaveParams,
        handler=upsert_source_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_citation": OperationEntry(
        name="upsert_citation",
        summary="Create or update a citation",
        description="Create or update citation including object associations",
        category="write",
        params_schema=CitationData,
        handler=upsert_citation_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_note": OperationEntry(
        name="upsert_note",
        summary="Create or update a textual note",
        description="Create or update textual note including object associations",
        category="write",
        params_schema=NoteSaveParams,
        handler=upsert_note_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_media": OperationEntry(
        name="upsert_media",
        summary="Create or update a media record with optional file upload",
        description=(
            "Create or update a media record (photo, document, etc.) and its metadata. "
            "When creating (no handle): provide file_location as an absolute local "
            "file path -- the file is uploaded and a new record is created. "
            "When updating (provide handle): omit file_location; only metadata fields "
            "(desc, date, mime, etc.) are changed. "
            "Note: path is the Gramps-relative storage path, not the upload source."
        ),
        category="write",
        params_schema=MediaSaveParams,
        handler=upsert_media_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_repository": OperationEntry(
        name="upsert_repository",
        summary="Create or update a repository",
        description="Create or update repository information",
        category="write",
        params_schema=RepositoryData,
        handler=upsert_repository_tool,
        read_only=False,
        destructive=False,
    ),
    "upsert_tag": OperationEntry(
        name="upsert_tag",
        summary="Create or update a tag",
        description=(
            "Create a tag with name, color, and priority, or update an existing "
            "one by passing its handle. On update, omitted fields keep their "
            "stored value; tags have no list fields, so list_mode does not apply."
        ),
        category="write",
        params_schema=TagSaveParams,
        handler=upsert_tag_tool,
        read_only=False,
        destructive=False,
    ),
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
        description="Get recent changes/modifications to the family tree",
        category="analysis",
        params_schema=TransactionHistoryParams,
        handler=get_recent_changes_tool,
        read_only=True,
        destructive=False,
    ),
}

TABLE_OPERATIONS: dict[str, OperationEntry] = build_registry(
    ENTITY_RESOURCES, TABLE_OVERLAYS
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
    _HANDWRITTEN, TABLE_OPERATIONS, _OPERATION_ORDER
)
