# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
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
MCP tool registry and annotations.

This module contains the centralized tool registry, annotation presets, and
parameter models for all MCP tools. It is imported by server.py for dynamic
registration and by tests for validation.
"""

from typing import Any, Dict, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

# Import all parameter models
from .models.parameters.citation_params import CitationData
from .models.parameters.event_params import EventSaveParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaSaveParams
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

# Import all tool functions
from .models.parameters.tag_params import TagSaveParams, TagSearchParams
from .models.parameters.transactions_params import TransactionHistoryParams
from .tools import (
    delete_tool,
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
    list_tags_tool,
    search_text_tool,
    upsert_citation_tool,
    upsert_event_tool,
    upsert_family_tool,
    upsert_media_tool,
    upsert_note_tool,
    upsert_person_tool,
    upsert_place_tool,
    upsert_repository_tool,
    upsert_source_tool,
    upsert_tag_tool,
)
from .tools.search_basic import search_tool
from .tools.search_details import get_tool


# Simple analysis models for tools that use direct dict access
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


# MCP-5: Tool annotation presets for read, write, and delete operations.
# All tools set openWorldHint=True (external Gramps Web API).
_READ_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
_WRITE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
_DELETE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

# Tool registry - single source of truth for all tools
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Search & Retrieval Tools
    "search": {
        "description": (
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax. "
            "Note: person names use primary_name.first_name and "
            "primary_name.surname_list[0].surname (NOT 'name' or 'surname')"
        ),
        "schema": SimpleFindParams,
        "handler": search_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "search_text": {
        "description": (
            "Text search across all record types - matches literal text "
            "within records, not logical combinations"
        ),
        "schema": SimpleSearchParams,
        "handler": search_text_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get": {
        "description": "Get full details for any entity by handle or gramps_id",
        "schema": SimpleGetParams,
        "handler": get_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    # Data Management Tools
    "upsert_person": {
        "description": (
            "Create or update person information including family links, "
            "event associations, and alternate names (AKA, married names)"
        ),
        "schema": PersonData,
        "handler": upsert_person_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_family": {
        "description": "Create or update family unit including member relationships",
        "schema": FamilySaveParams,
        "handler": upsert_family_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_event": {
        "description": (
            "Create or update life event including person/place associations"
        ),
        "schema": EventSaveParams,
        "handler": upsert_event_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_place": {
        "description": "Create or update geographic location",
        "schema": PlaceSaveParams,
        "handler": upsert_place_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_source": {
        "description": "Create or update source document",
        "schema": SourceSaveParams,
        "handler": upsert_source_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_citation": {
        "description": "Create or update citation including object associations",
        "schema": CitationData,
        "handler": upsert_citation_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_note": {
        "description": "Create or update textual note including object associations",
        "schema": NoteSaveParams,
        "handler": upsert_note_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_media": {
        "description": (
            "Create or update a media record (photo, document, etc.) and its metadata. "
            "When creating (no handle): provide file_location as an absolute local "
            "file path — the file is uploaded and a new record is created. "
            "When updating (provide handle): omit file_location; only metadata fields "
            "(desc, date, mime, etc.) are changed. "
            "Note: path is the Gramps-relative storage path, not the upload source."
        ),
        "schema": MediaSaveParams,
        "handler": upsert_media_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "upsert_repository": {
        "description": "Create or update repository information",
        "schema": RepositoryData,
        "handler": upsert_repository_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "delete": {
        "description": "Delete any entity by type and handle",
        "schema": DeleteParams,
        "handler": delete_tool,
        "annotations": _DELETE_ANNOTATIONS,
    },
    # Tag Management Tools
    "upsert_tag": {
        "description": (
            "Create a tag with name and color. Tags are immutable after creation "
            "in API 3.x -- to change a tag, delete and recreate it."
        ),
        "schema": TagSaveParams,
        "handler": upsert_tag_tool,
        "annotations": _WRITE_ANNOTATIONS,
    },
    "list_tags": {
        "description": "List all tags in the family tree",
        "schema": TagSearchParams,
        "handler": list_tags_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    # Analysis Tools
    "get_tree_stats": {
        "description": (
            "Get information about a specific tree including statistics "
            "(counts of people, families, events, etc.)"
        ),
        "schema": TreeInfoParams,
        "handler": get_tree_stats_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get_descendants": {
        "description": (
            "Find all descendants of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": DescendantsParams,
        "handler": get_descendants_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get_ancestors": {
        "description": (
            "Find all ancestors of a person - WARNING: Very token-heavy "
            "operation, minimize generations (default: 5)"
        ),
        "schema": AncestorsParams,
        "handler": get_ancestors_tool,
        "annotations": _READ_ANNOTATIONS,
    },
    "get_recent_changes": {
        "description": "Get recent changes/modifications to the family tree",
        "schema": TransactionHistoryParams,
        "handler": get_recent_changes_tool,
        "annotations": _READ_ANNOTATIONS,
    },
}
