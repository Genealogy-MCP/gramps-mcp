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
Family data handler for Gramps MCP operations.

Provides clean, direct formatting of family data from handles.
"""

import logging

from ..models.api_calls import ApiCalls
from .date_handler import format_date
from .place_handler import format_place

logger = logging.getLogger(__name__)


async def format_family(client, tree_id: str, handle: str) -> str:
    """
    Format family data with members and basic details.

    Args:
        client: Gramps API client instance
        tree_id (str): Family tree identifier
        handle (str): Family handle

    Returns:
        str: Formatted family string with members and details
    """
    if not handle:
        return "• **Family**\n  No handle provided\n\n"

    try:
        # Get family data with extended information
        family_data = await client.make_api_call(
            ApiCalls.GET_FAMILY,
            tree_id=tree_id,
            handle=handle,
            params={"extend": "all"},
        )
        if not family_data:
            return f"• **Family {handle}**\n  Family not found\n\n"

        gramps_id = family_data.get("gramps_id", "")
        extended = family_data.get("extended", {})
        result = ""

        # First line: Father: Name (Gender) - ID | Mother: Name (Gender) - ID
        # - FamilyID - [family_handle]
        family_members = []

        # Get father (from extend=all, avoids extra API call)
        father = extended.get("father", {})
        if father and isinstance(father, dict) and father.get("gramps_id"):
            father_name = _extract_person_name(father)
            father_gender = _get_gender_letter(father.get("gender", 2))
            father_id = father.get("gramps_id", "")
            family_members.append(
                f"Father: {father_name} ({father_gender}) - {father_id}"
            )

        # Get mother (from extend=all, avoids extra API call)
        mother = extended.get("mother", {})
        if mother and isinstance(mother, dict) and mother.get("gramps_id"):
            mother_name = _extract_person_name(mother)
            mother_gender = _get_gender_letter(mother.get("gender", 2))
            mother_id = mother.get("gramps_id", "")
            family_members.append(
                f"Mother: {mother_name} ({mother_gender}) - {mother_id}"
            )

        # First line with family ID and handle
        if family_members:
            result += f"{' | '.join(family_members)} - {gramps_id} - [{handle}]\n"
        else:
            result += f"{gramps_id} - [{handle}]\n"

        # Marriage and divorce events
        events = extended.get("events", [])
        event_ref_list = family_data.get("event_ref_list", [])

        for i, event_ref in enumerate(event_ref_list):
            if i < len(events):
                event = events[i]
                event_type = event.get("type", "")

                if event_type.lower() == "marriage":
                    marriage_date = format_date(event.get("date", {}))
                    marriage_place = await format_place(
                        client, tree_id, event.get("place", ""), inline=True
                    )
                    if marriage_date or marriage_place:
                        result += f"Married: {marriage_date}"
                        if marriage_place:
                            result += f" - {marriage_place}"
                        result += "\n"

                elif event_type.lower() == "divorce":
                    divorce_date = format_date(event.get("date", {}))
                    divorce_place = await format_place(
                        client, tree_id, event.get("place", ""), inline=True
                    )
                    if divorce_date or divorce_place:
                        result += f"Divorced: {divorce_date}"
                        if divorce_place:
                            result += f" - {divorce_place}"
                        result += "\n"

        # Children (from extend=all, avoids N+1 API calls)
        extended_children = extended.get("children", [])
        if extended_children:
            child_names = []
            for child_data in extended_children:
                if not isinstance(child_data, dict) or not child_data.get("gramps_id"):
                    continue
                child_name = _extract_person_name(child_data)
                child_gender = _get_gender_letter(child_data.get("gender", 2))
                child_id = child_data.get("gramps_id", "")
                child_names.append(f"{child_name} ({child_gender}) - {child_id}")

            if child_names:
                result += f"Children: {', '.join(child_names)}\n"

        # Events (all events with roles)
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
        urls = family_data.get("urls", [])
        if urls:
            for url in urls:
                if isinstance(url, dict):
                    url_path = url.get("path", "")
                    url_desc = url.get("desc", "")
                    if url_path:
                        if url_desc:
                            result += f"{url_path} - {url_desc}\n"
                        else:
                            result += f"{url_path}\n"

        return result + "\n"

    except Exception as e:
        logger.warning(f"Failed to format family {handle}: {e}")
        return f"• **Family {handle}**\n  Error formatting family: {str(e)}\n\n"


def _extract_person_name(person_data: dict) -> str:
    """Extract full name from person data."""
    primary_name = person_data.get("primary_name", {})
    if primary_name:
        given_name = primary_name.get("first_name", "")
        surname_list = primary_name.get("surname_list", [])
        surname = surname_list[0].get("surname", "") if surname_list else ""
        full_name = f"{given_name} {surname}".strip()
        return full_name if full_name else ""
    return ""


def _get_gender_letter(gender: int) -> str:
    """Convert gender number to letter."""
    return {0: "F", 1: "M", 2: "U"}.get(gender, "U")
