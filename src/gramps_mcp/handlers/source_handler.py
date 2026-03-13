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
Source data handler for Gramps MCP operations.

Provides clean, direct formatting of source data from handles.
"""

import logging

from ..models.api_calls import ApiCalls

logger = logging.getLogger(__name__)


async def format_source(client, tree_id: str, handle: str) -> str:
    """
    Format source data with title, author, and publication details.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Source handle

    Returns:
        Formatted source string with details
    """
    if not handle:
        return "• **Unknown Source**\n  No handle provided\n\n"

    try:
        source_data = await client.make_api_call(
            api_call=ApiCalls.GET_SOURCE,
            tree_id=tree_id,
            handle=handle,
            params={"extend": "all"},
        )
        if not source_data:
            return f"• **Source {handle}**\n  Source not found\n\n"

        gramps_id = source_data.get("gramps_id", "")
        title = source_data.get("title", "").strip()
        author = source_data.get("author", "").strip()
        pubinfo = source_data.get("pubinfo", "").strip()
        extended = source_data.get("extended", {})

        # First line: Title - gramps_id - [handle]
        first_line = f"{title} - {gramps_id} - [{handle}]"
        result = first_line

        # Second line: author - pub info (if available)
        if author or pubinfo:
            second_line_parts = []
            if author:
                second_line_parts.append(author)
            if pubinfo:
                second_line_parts.append(pubinfo)
            result += f"\n{' - '.join(second_line_parts)}"

        # Repository info (from extend=all, avoids N+1 API calls)
        extended_repos = extended.get("repositories", [])
        for repo_data in extended_repos:
            if not isinstance(repo_data, dict):
                continue
            repo_name = repo_data.get("name", "").strip()
            repo_gramps_id = repo_data.get("gramps_id", "")
            if repo_name and repo_gramps_id:
                result += f"\n{repo_name} - {repo_gramps_id}"

        # Attached media (from extend=all, avoids N+1 API calls)
        extended_media = extended.get("media", [])
        if extended_media:
            media_ids = [
                m.get("gramps_id", "")
                for m in extended_media
                if isinstance(m, dict) and m.get("gramps_id")
            ]
            if media_ids:
                result += f"\nAttached media: {', '.join(media_ids)}"

        # Attached notes (from extend=all, avoids N+1 API calls)
        extended_notes = extended.get("notes", [])
        if extended_notes:
            note_ids = [
                n.get("gramps_id", "")
                for n in extended_notes
                if isinstance(n, dict) and n.get("gramps_id")
            ]
            if note_ids:
                result += f"\nAttached notes: {', '.join(note_ids)}"

        return result + "\n\n"

    except Exception as e:
        logger.warning(f"Failed to format source {handle}: {e}")
        return f"• **Source {handle}**\n  Error formatting source: {str(e)}\n\n"
