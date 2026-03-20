# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 Federico Castagnini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Operation registry for Code Mode architecture (MCP-29 through MCP-34).

Single source of truth for all available operations. Each entry describes
an operation's name, category, parameter schema, handler function, and
behavioral hints. The ``search`` meta-tool queries this registry; the
``execute`` meta-tool dispatches to the handler.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from .models.parameters.citation_params import CitationData
from .models.parameters.event_params import EventSaveParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaDownloadParams, MediaSaveParams
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.simple_params import (
    DeleteParams,
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.tag_params import TagSaveParams, TagSearchParams
from .models.parameters.transactions_params import TransactionHistoryParams

# Import handlers directly from sub-modules (not tools/__init__.py)
# to avoid circular imports — meta_execute/meta_search live in tools/
# and import from this module.
from .tools.analysis import (
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
)
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
from .tools.data_management_delete import delete_tool, upsert_tag_tool
from .tools.data_management_media import download_media_tool, upsert_media_tool
from .tools.search_basic import list_tags_tool, search_text_tool, search_tool
from .tools.search_details import get_tool

# ---------------------------------------------------------------------------
# Parameter models for analysis tools (moved from server_tools.py)
# ---------------------------------------------------------------------------


class TreeInfoParams(BaseModel):
    include_statistics: bool = Field(True, description="Include statistics")


class DescendantsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


class AncestorsParams(BaseModel):
    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(
        5,
        description=(
            "Max generations to retrieve (default: 5, use higher values "
            "carefully as they can overflow context)"
        ),
    )


# ---------------------------------------------------------------------------
# OperationEntry dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperationEntry:
    """Describes a single operation in the registry.

    Args:
        name: Stable snake_case identifier (e.g. "upsert_person").
        summary: One-line description for search results.
        description: Full description (shown on ``execute`` errors or docs).
        category: One of "search", "read", "write", "delete", "analysis".
        params_schema: Pydantic model class for parameter validation.
        handler: Async handler function that performs the operation.
        read_only: True if the operation does not mutate data.
        destructive: True if the operation deletes data.
        token_warning: Optional warning about token-heavy output.
    """

    name: str
    summary: str
    description: str
    category: str
    params_schema: type
    handler: Callable[..., Any]
    read_only: bool
    destructive: bool
    token_warning: str | None = field(default=None)


# ---------------------------------------------------------------------------
# OPERATION_REGISTRY — 20 operations
# ---------------------------------------------------------------------------

OPERATION_REGISTRY: dict[str, OperationEntry] = {
    # --- search (3) ---
    "search": OperationEntry(
        name="search",
        summary="Search any entity type using GQL queries",
        description=(
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax. "
            "Note: person names use primary_name.first_name and "
            "primary_name.surname_list[0].surname (NOT 'name' or 'surname')"
        ),
        category="search",
        params_schema=SimpleFindParams,
        handler=search_tool,
        read_only=True,
        destructive=False,
    ),
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
    "list_tags": OperationEntry(
        name="list_tags",
        summary="List all tags in the family tree",
        description="List all tags in the family tree",
        category="search",
        params_schema=TagSearchParams,
        handler=list_tags_tool,
        read_only=True,
        destructive=False,
    ),
    # --- read (3) ---
    "get": OperationEntry(
        name="get",
        summary="Get full details for any entity by handle or gramps_id",
        description="Get full details for any entity by handle or gramps_id",
        category="read",
        params_schema=SimpleGetParams,
        handler=get_tool,
        read_only=True,
        destructive=False,
    ),
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
    # --- write (10) ---
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
        summary="Create a tag (immutable after creation in API 3.x)",
        description=(
            "Create a tag with name and color. Tags are immutable after creation "
            "in API 3.x -- to change a tag, delete and recreate it."
        ),
        category="write",
        params_schema=TagSaveParams,
        handler=upsert_tag_tool,
        read_only=False,
        destructive=False,
    ),
    # --- delete (1) ---
    "delete": OperationEntry(
        name="delete",
        summary="Delete any entity by type and handle",
        description="Delete any entity by type and handle",
        category="delete",
        params_schema=DeleteParams,
        handler=delete_tool,
        read_only=False,
        destructive=True,
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


# ---------------------------------------------------------------------------
# Search algorithm
# ---------------------------------------------------------------------------


def search_operations(
    query: str,
    *,
    category: str | None = None,
    max_results: int = 10,
) -> list[OperationEntry]:
    """Search the operation registry by keyword.

    Scoring:
    - +3 for exact name match
    - +2 for query token found in operation name
    - +1 for query token found in summary or description

    Args:
        query: Free-text search query.
        category: Optional category filter (search/read/write/delete/analysis).
        max_results: Maximum number of results to return (default: 10).

    Returns:
        List of matching OperationEntry objects, ordered by score descending.
    """
    candidates = OPERATION_REGISTRY.values()
    if category:
        candidates = [e for e in candidates if e.category == category]

    if not query.strip():
        return list(candidates)[:max_results]

    tokens = query.lower().split()
    scored: list[tuple[int, OperationEntry]] = []

    for entry in candidates:
        score = 0
        name_lower = entry.name.lower()
        searchable = f"{entry.summary} {entry.description}".lower()

        if query.lower() == name_lower:
            score += 3

        for token in tokens:
            if token in name_lower:
                score += 2
            if token in searchable:
                score += 1

        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:max_results]]


# ---------------------------------------------------------------------------
# Parameter summarization
# ---------------------------------------------------------------------------


def summarize_params(schema: type) -> list[dict[str, Any]]:
    """Produce a condensed parameter summary from a Pydantic model.

    Args:
        schema: A Pydantic BaseModel subclass.

    Returns:
        List of dicts with keys: name, type, required, description.
    """
    if not hasattr(schema, "model_fields"):
        return []

    result: list[dict[str, Any]] = []
    for name, field_info in schema.model_fields.items():
        annotation = field_info.annotation
        type_str = getattr(annotation, "__name__", str(annotation))
        result.append(
            {
                "name": name,
                "type": type_str,
                "required": field_info.is_required(),
                "description": field_info.description or "",
            }
        )
    return result
