# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Unified interface for all MCP tools.

This module re-exports per-type tool functions used by
tools/__init__.py consumers. Operations are registered in
OPERATION_REGISTRY (operations.py).
"""

# Analysis Tools
from .analysis import (
    get_ancestors_tool,
    get_descendants_tool,
    get_recent_changes_tool,
    get_tree_stats_tool,
)

# Backup Tools
from .backups import create_backup_tool, list_backups_tool

# Data Management Tools: delete and media download have their own modules;
# every upsert is the generic table-driven handler (#102, #103).
from .data_management_delete import delete_tool
from .data_management_media import download_media_tool
from .search_basic import (
    list_tags_tool,
    search_citation_tool,
    search_event_tool,
    search_family_tool,
    search_media_tool,
    search_person_tool,
    search_place_tool,
    search_repository_tool,
    search_source_tool,
    search_text_tool,
)
from .search_details import (
    get_family_tool,
    get_person_tool,
)
from .upsert_table import UPSERT_HANDLERS

upsert_person_tool = UPSERT_HANDLERS["person"]
upsert_family_tool = UPSERT_HANDLERS["family"]
upsert_event_tool = UPSERT_HANDLERS["event"]
upsert_place_tool = UPSERT_HANDLERS["place"]
upsert_source_tool = UPSERT_HANDLERS["source"]
upsert_citation_tool = UPSERT_HANDLERS["citation"]
upsert_note_tool = UPSERT_HANDLERS["note"]
upsert_media_tool = UPSERT_HANDLERS["media"]
upsert_repository_tool = UPSERT_HANDLERS["repository"]
upsert_tag_tool = UPSERT_HANDLERS["tag"]

# Export all tools for easy import
__all__ = [
    # Search & Discovery Tools
    "search_person_tool",
    "search_family_tool",
    "search_event_tool",
    "search_place_tool",
    "search_source_tool",
    "search_repository_tool",
    "search_citation_tool",
    "search_media_tool",
    "search_text_tool",
    "get_person_tool",
    "get_family_tool",
    # Data Management Tools
    "upsert_person_tool",
    "upsert_family_tool",
    "upsert_event_tool",
    "upsert_place_tool",
    "upsert_source_tool",
    "upsert_citation_tool",
    "upsert_note_tool",
    "upsert_media_tool",
    "download_media_tool",
    "upsert_repository_tool",
    "delete_tool",
    "upsert_tag_tool",
    # Search Tools
    "list_tags_tool",
    # Analysis Tools
    "get_tree_stats_tool",
    "get_descendants_tool",
    "get_ancestors_tool",
    "get_recent_changes_tool",
    # Backup Tools
    "create_backup_tool",
    "list_backups_tool",
]
