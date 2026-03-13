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
Repository data handler for Gramps MCP operations.

Provides clean, direct formatting of repository data from handles.
"""

import logging

from ..models.api_calls import ApiCalls

logger = logging.getLogger(__name__)


async def format_repository(client, tree_id: str, handle: str) -> str:
    """
    Format repository data with name and type.

    Args:
        client: Gramps API client instance
        tree_id: Family tree identifier
        handle: Repository handle

    Returns:
        Formatted repository string with details
    """
    if not handle:
        return ""

    try:
        repo_data = await client.make_api_call(
            api_call=ApiCalls.GET_REPOSITORY,
            tree_id=tree_id,
            handle=handle,
            params={"extend": "all"},
        )
        if not repo_data:
            return ""

        gramps_id = repo_data.get("gramps_id", "")
        name = repo_data.get("name", "").strip()
        repo_type = repo_data.get("type", "")

        # First line: type: name - gramps_id - [handle]
        first_line = f"{repo_type}: {name} - {gramps_id} - [{handle}]"
        result = first_line

        # Add URLs if present
        urls = repo_data.get("urls", [])
        for url in urls:
            path = url.get("path", "")
            desc = url.get("desc", "")
            if path:
                url_line = path
                if desc:
                    url_line += f" - {desc}"
                result += f"\n{url_line}"

        # Attached notes (from extend=all, avoids N+1 API calls)
        extended = repo_data.get("extended", {})
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
        logger.warning(f"Failed to format repository {handle}: {e}")
        return ""
