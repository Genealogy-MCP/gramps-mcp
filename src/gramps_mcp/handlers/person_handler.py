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
Person data handler for Gramps MCP operations.

Provides clean, direct formatting of person data from handles.
"""

import logging

from ..models.api_calls import ApiCalls
from .date_handler import format_date
from .place_handler import format_place

logger = logging.getLogger(__name__)


async def format_person(client, tree_id: str, handle: str) -> str:
    """
    Format person data directly from handle into display string.

    Args:
        client: Gramps API client instance
        tree_id (str): Family tree identifier
        handle (str): Person handle

    Returns:
        str: Formatted person string ready for display
    """
    try:
        # Get person data with extended information
        person_data = await client.make_api_call(
            ApiCalls.GET_PERSON,
            tree_id=tree_id,
            handle=handle,
            params={"extend": "all"},
        )
        if not person_data:
            return f"• **Unknown Person** (Handle: {handle})\n  No data available\n\n"

        # Extract basic info
        gramps_id = person_data.get("gramps_id", "")

        # Extract name inline
        name = ""
        primary_name = person_data.get("primary_name", {})
        if primary_name:
            given_name = primary_name.get("first_name", "")
            surname_list = primary_name.get("surname_list", [])
            surname = surname_list[0].get("surname", "") if surname_list else ""
            full_name = f"{given_name} {surname}".strip()
            if full_name:
                name = full_name

        # Get gender information
        gender = person_data.get("gender", 2)  # Default to Unknown
        gender_letter = {0: "F", 1: "M", 2: "U"}
        gender_display = gender_letter.get(gender, "U")

        # First line: Name (gender) - gramps_id - [handle]
        result = f"{name} ({gender_display}) - {gramps_id} - [{handle}]\n"

        # Get birth and death events
        extended = person_data.get("extended", {})
        events = extended.get("events", [])

        # Birth event
        birth_ref_index = person_data.get("birth_ref_index", -1)
        event_ref_list = person_data.get("event_ref_list", [])
        if (
            birth_ref_index >= 0
            and birth_ref_index < len(event_ref_list)
            and birth_ref_index < len(events)
        ):
            birth_event = events[birth_ref_index]
            birth_date = format_date(birth_event.get("date", {}))
            birth_place = await format_place(
                client, tree_id, birth_event.get("place", ""), inline=True
            )
            result += f"Born: {birth_date} - {birth_place}\n"

        # Death event
        death_ref_index = person_data.get("death_ref_index", -1)
        if (
            death_ref_index >= 0
            and death_ref_index < len(event_ref_list)
            and death_ref_index < len(events)
        ):
            death_event = events[death_ref_index]
            death_date = format_date(death_event.get("date", {}))
            death_place = await format_place(
                client, tree_id, death_event.get("place", ""), inline=True
            )
            result += f"Died: {death_date} - {death_place}\n"

        # Family relationships
        family_relationships = []

        # As child
        parent_families = extended.get("parent_families", [])
        for family in parent_families:
            family_gramps_id = family.get("gramps_id", "")
            family_relationships.append(f"child ({family_gramps_id})")

        # As parent
        families = extended.get("families", [])
        for family in families:
            family_gramps_id = family.get("gramps_id", "")
            family_relationships.append(f"parent ({family_gramps_id})")

        if family_relationships:
            result += f"Family member of: {', '.join(family_relationships)}\n"

        # Events (include all events)
        event_list = []
        for i, event_ref in enumerate(event_ref_list):
            if i < len(events):
                event = events[i]
                event_type = event.get("type", "")
                event_gramps_id = event.get("gramps_id", "")

                # Get role from event_ref
                role = event_ref.get("role", "") if isinstance(event_ref, dict) else ""
                if role:
                    event_list.append(f"{event_type}, {role} ({event_gramps_id})")
                else:
                    event_list.append(f"{event_type} ({event_gramps_id})")

        if event_list:
            result += f"Events: {', '.join(event_list)}\n"

        # Attached media (from extend=all, avoids N+1 API calls)
        extended_media = extended.get("media", [])
        if extended_media:
            media_ids = [
                m.get("gramps_id", "")
                for m in extended_media
                if isinstance(m, dict) and m.get("gramps_id")
            ]
            if media_ids:
                result += f"Attached media: {', '.join(media_ids)}\n"

        # Attached notes (from extend=all, avoids N+1 API calls)
        extended_notes = extended.get("notes", [])
        if extended_notes:
            note_ids = [
                n.get("gramps_id", "")
                for n in extended_notes
                if isinstance(n, dict) and n.get("gramps_id")
            ]
            if note_ids:
                result += f"Attached notes: {', '.join(note_ids)}\n"

        # URLs
        urls = person_data.get("urls", [])
        if urls:
            for url in urls:
                if isinstance(url, dict):
                    url_path = url.get("path", "")
                    url_desc = url.get("description", "")
                    if url_path:
                        if url_desc:
                            result += f"{url_path} - {url_desc}\n"
                        else:
                            result += f"{url_path}\n"

        return result + "\n"

    except Exception as e:
        logger.warning(f"Failed to format person {handle}: {e}")
        return f"• **Error formatting person** (Handle: {handle})\n  {str(e)}\n\n"
