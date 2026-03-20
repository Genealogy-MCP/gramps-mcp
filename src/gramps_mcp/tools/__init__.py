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

# Data Management Tools -- split across submodules by responsibility:
# data_management (CRUD), data_management_delete (delete + tags),
# data_management_media (media upload).
from .data_management import (
    upsert_citation_tool,
    upsert_event_tool,
    upsert_family_tool,
    upsert_note_tool,
    upsert_person_tool,
    upsert_place_tool,
    upsert_repository_tool,
    upsert_source_tool,
)
from .data_management_delete import delete_tool, upsert_tag_tool
from .data_management_media import download_media_tool, upsert_media_tool

# Meta-tools (Code Mode) are NOT re-exported here to avoid circular
# imports: meta_execute/meta_search depend on operations.py, which
# imports handler functions from this package. Import them directly
# from tools.meta_search / tools.meta_execute where needed.
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
]
