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
Person detail handler for Gramps MCP operations.
"""

import logging

from ..models.api_calls import ApiCalls
from .date_handler import format_date
from .name_utils import join_surnames
from .place_handler import format_place

logger = logging.getLogger(__name__)


async def format_person_detail(client, tree_id: str, handle: str) -> str:
    """Format comprehensive person data with timeline and citations."""
    # Get person data
    person_data = await client.make_api_call(
        ApiCalls.GET_PERSON, tree_id=tree_id, handle=handle, params={"extend": "all"}
    )

    # Get person timeline
    timeline_data = await client.make_api_call(
        ApiCalls.GET_PERSON_TIMELINE,
        tree_id=tree_id,
        handle=handle,
        params={"ratings": True},  # Include citation confidence
    )

    result = "=== PERSON DETAILS ===\n"

    # Extract basic info
    gramps_id = person_data.get("gramps_id", "")
    extended = person_data.get("extended", {})

    # Build handle -> gramps_id map from person-level extended citations
    citation_map: dict[str, str] = {}
    for c in extended.get("citations", []):
        if isinstance(c, dict) and c.get("handle") and c.get("gramps_id"):
            citation_map[c["handle"]] = c["gramps_id"]

    name = _extract_person_name(person_data)
    gender_display = _get_gender_letter(person_data.get("gender", 2))

    # Resolve primary name citations
    primary_name = person_data.get("primary_name", {})
    primary_cit_handles = primary_name.get("citation_list", []) if primary_name else []
    primary_cit_ids = [
        citation_map[h] for h in primary_cit_handles if h in citation_map
    ]
    primary_cit_part = f" [{', '.join(primary_cit_ids)}]" if primary_cit_ids else ""

    header = f"{name} ({gender_display}) - {gramps_id} - [{handle}]"
    result += f"{header}{primary_cit_part}\n"

    # Alternate names
    alt_names = person_data.get("alternate_names", [])
    if alt_names:
        result += "Alternate names:\n"
        for alt_name in alt_names:
            if not isinstance(alt_name, dict):
                continue
            name_type_raw = alt_name.get("type", "")
            name_type = (
                name_type_raw.get("string", "")
                if isinstance(name_type_raw, dict)
                else str(name_type_raw)
            )
            given = alt_name.get("first_name", "")
            alt_surname = join_surnames(alt_name.get("surname_list", []))
            full = f"{given} {alt_surname}".strip()
            if not full:
                continue
            cit_handles = alt_name.get("citation_list", [])
            cit_ids = [citation_map[h] for h in cit_handles if h in citation_map]
            cit_part = f" [{', '.join(cit_ids)}]" if cit_ids else ""
            prefix = f"{name_type}: " if name_type else ""
            result += f"  - {prefix}{full}{cit_part}\n"

    # Birth and death from extended data
    events = extended.get("events", [])

    # Birth event
    birth_ref_index = person_data.get("birth_ref_index", -1)
    if birth_ref_index >= 0 and birth_ref_index < len(events):
        birth_event = events[birth_ref_index]
        birth_date = format_date(birth_event.get("date", {}))
        birth_place = await format_place(
            client, tree_id, birth_event.get("place", ""), inline=True
        )
        result += f"Born: {birth_date} - {birth_place}\n"

    # Death event
    death_ref_index = person_data.get("death_ref_index", -1)
    if death_ref_index >= 0 and death_ref_index < len(events):
        death_event = events[death_ref_index]
        death_date = format_date(death_event.get("date", {}))
        death_place = await format_place(
            client, tree_id, death_event.get("place", ""), inline=True
        )
        result += f"Died: {death_date} - {death_place}\n"

    # Relations section
    result += "\nRELATIONS:\n"

    # Parents section
    result += "Parents:\n"
    parent_family_list = person_data.get("parent_family_list", [])

    for family_handle in parent_family_list:
        try:
            family_data = await client.make_api_call(
                ApiCalls.GET_FAMILY,
                tree_id=tree_id,
                handle=family_handle,
                params={"extend": "all"},
            )
            extended = family_data.get("extended", {})

            # Father
            father = extended.get("father", {})
            if father:
                father_name = _extract_person_name(father)
                father_id = father.get("gramps_id", "")
                father_birth, father_death = await _get_birth_death_dates(
                    client, tree_id, father
                )
                dates = ", ".join(filter(None, [father_birth, father_death]))
                result += f"- {father_name} - {father_id} - {dates}\n"

            # Mother
            mother = extended.get("mother", {})
            if mother:
                mother_name = _extract_person_name(mother)
                mother_id = mother.get("gramps_id", "")
                mother_birth, mother_death = await _get_birth_death_dates(
                    client, tree_id, mother
                )
                dates = ", ".join(filter(None, [mother_birth, mother_death]))
                result += f"- {mother_name} - {mother_id} - {dates}\n"

            # Siblings (other children in same family)
            children = extended.get("children", [])
            siblings = [
                child for child in children if child.get("gramps_id", "") != gramps_id
            ]
            if siblings:
                result += "Siblings:\n"
                for sibling in siblings:
                    sibling_name = _extract_person_name(sibling)
                    sibling_id = sibling.get("gramps_id", "")
                    sibling_birth, sibling_death = await _get_birth_death_dates(
                        client, tree_id, sibling
                    )
                    dates = ", ".join(filter(None, [sibling_birth, sibling_death]))
                    result += f"- {sibling_name} - {sibling_id} - {dates}\n"

        except Exception as e:
            logger.warning(f"Failed to fetch parent family {family_handle}: {e}")
            continue

    # Spouses and children
    family_list = person_data.get("family_list", [])
    for family_handle in family_list:
        try:
            family_data = await client.make_api_call(
                ApiCalls.GET_FAMILY,
                tree_id=tree_id,
                handle=family_handle,
                params={"extend": "all"},
            )
            extended = family_data.get("extended", {})

            # Determine spouse (father or mother that's not this person)
            father = extended.get("father", {})
            mother = extended.get("mother", {})

            spouse = None
            if father and father.get("gramps_id", "") != gramps_id:
                spouse = father
            elif mother and mother.get("gramps_id", "") != gramps_id:
                spouse = mother

            if spouse:
                spouse_name = _extract_person_name(spouse)
                spouse_id = spouse.get("gramps_id", "")
                spouse_birth, spouse_death = await _get_birth_death_dates(
                    client, tree_id, spouse
                )
                dates = ", ".join(filter(None, [spouse_birth, spouse_death]))
                result += f"Spouse:\n- {spouse_name} - {spouse_id} - {dates}\n"

                # Children of this spouse
                children = extended.get("children", [])
                if children:
                    result += "Children:\n"
                    for child in children:
                        child_name = _extract_person_name(child)
                        child_id = child.get("gramps_id", "")
                        child_birth, child_death = await _get_birth_death_dates(
                            client, tree_id, child
                        )
                        dates = ", ".join(filter(None, [child_birth, child_death]))
                        result += f"- {child_name} - {child_id} - {dates}\n"
        except Exception as e:
            logger.warning(f"Failed to fetch spouse family {family_handle}: {e}")
            continue

    # Timeline section
    result += "\nTIMELINE:\n"
    if timeline_data:
        for timeline_event in timeline_data:
            if not isinstance(timeline_event, dict):
                continue

            # Basic event info from timeline
            event_type = timeline_event.get("type", "Unknown")
            event_id = timeline_event.get("gramps_id", "")
            role = timeline_event.get("role", "Primary")
            event_handle = timeline_event.get("handle", "")

            # Get properly formatted date using format_date function
            event_date = "date unknown"
            event_data = None
            if event_handle:
                try:
                    event_data = await client.make_api_call(
                        ApiCalls.GET_EVENT,
                        tree_id=tree_id,
                        handle=event_handle,
                        params={"extend": "all"},
                    )
                    event_date = format_date(event_data.get("date", {}))
                except Exception as e:
                    logger.warning(f"Failed to fetch event {event_handle}: {e}")
                    event_date = timeline_event.get("date", "date unknown")

            # Place - use display_name directly from timeline data
            place_data = timeline_event.get("place", {})
            place_name = (
                place_data.get("display_name", "")
                if isinstance(place_data, dict)
                else ""
            )
            place_part = f"({place_name})" if place_name else "()"

            # Participant info - extract from person data in timeline
            participant_name = ""
            participant_id = ""
            person_data_in_timeline = timeline_event.get("person", {})

            if person_data_in_timeline:
                relationship = person_data_in_timeline.get("relationship", "")
                if relationship == "self":
                    # This person's event
                    participant_name = _extract_person_name(person_data)
                    participant_id = person_data.get("gramps_id", "")
                else:
                    # Other person's event - use data from timeline
                    given_name = person_data_in_timeline.get("name_given", "")
                    surname = person_data_in_timeline.get("name_surname", "")
                    participant_name = f"{given_name} {surname}".strip()
                    participant_id = person_data_in_timeline.get("gramps_id", "")

            # Format the timeline entry
            participant_part = (
                f", {participant_name} {participant_id}, {role}"
                if participant_name
                else f", {role}"
            )
            result += (
                f"- {event_date} {place_part} - {event_id} : "
                f"{event_type}{participant_part}\n"
            )

            # Add citations from event's extended data (avoids N+1 API calls)
            if event_data:
                try:
                    event_extended = event_data.get("extended", {})
                    extended_citations = event_extended.get("citations", [])
                    if extended_citations:
                        citation_ids = [
                            c.get("gramps_id", "")
                            for c in extended_citations
                            if isinstance(c, dict) and c.get("gramps_id")
                        ]
                        if citation_ids:
                            result += f"  Citations: {', '.join(citation_ids)}\n"
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch citations for event {event_handle}: {e}"
                    )

    # Attached media section (from person's extend=all data)
    result += "\nAttached media:\n"
    person_extended = person_data.get("extended", {})
    extended_media = person_extended.get("media", [])
    for media_obj in extended_media:
        if isinstance(media_obj, dict):
            media_desc = media_obj.get("desc", "")
            media_id = media_obj.get("gramps_id", "")
            result += f"- {media_desc} ({media_id})\n"

    # Attached notes section (from person's extend=all data)
    result += "\nAttached notes:\n"
    extended_notes = person_extended.get("notes", [])
    for note_obj in extended_notes:
        if isinstance(note_obj, dict):
            note_type = note_obj.get("type", "")
            note_id = note_obj.get("gramps_id", "")
            note_text_raw = note_obj.get("text", "")
            # Handle StyledText format
            if isinstance(note_text_raw, dict):
                note_text_raw = note_text_raw.get("string", "")
            note_text = note_text_raw[:50]
            if len(note_text_raw) > 50:
                note_text += "..."
            result += f"- {note_type}: {note_text} ({note_id})\n"

    return result


def _extract_person_name(person_data: dict) -> str:
    """Extract full name from person data."""
    primary_name = person_data.get("primary_name", {})
    if primary_name:
        given_name = primary_name.get("first_name", "")
        surname_list = primary_name.get("surname_list", [])
        surname = join_surnames(surname_list)
        return f"{given_name} {surname}".strip()
    return "Unknown"


def _get_gender_letter(gender: int) -> str:
    """Convert gender number to letter."""
    return {0: "F", 1: "M", 2: "U"}.get(gender, "U")


async def _get_birth_death_dates(client, tree_id: str, person_data: dict) -> tuple:
    """Get birth and death dates for a person."""
    person_handle = person_data.get("handle", "")
    if not person_handle:
        return "", ""

    try:
        # Get person with extended data to access events
        full_person_data = await client.make_api_call(
            ApiCalls.GET_PERSON,
            tree_id=tree_id,
            handle=person_handle,
            params={"extend": "all"},
        )

        extended = full_person_data.get("extended", {})
        events = extended.get("events", [])

        birth_date = ""
        death_date = ""

        # Check for birth event
        birth_ref_index = full_person_data.get("birth_ref_index", -1)
        if birth_ref_index >= 0 and birth_ref_index < len(events):
            birth_event = events[birth_ref_index]
            birth_date = format_date(birth_event.get("date", {}))

        # Check for death event
        death_ref_index = full_person_data.get("death_ref_index", -1)
        if death_ref_index >= 0 and death_ref_index < len(events):
            death_event = events[death_ref_index]
            death_date = format_date(death_event.get("date", {}))

        # If still living, show as such
        if full_person_data.get("living", False):
            death_date = "Living"

        return birth_date, death_date

    except Exception as e:
        logger.warning(f"Failed to get birth/death dates for {person_handle}: {e}")
        return "", ""
