# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Family detail handler for Gramps MCP operations.
"""

import logging

from ..models.api_calls import ApiCalls
from ..utils import gather_bounded
from .date_handler import format_date
from .name_utils import join_surnames
from .place_handler import format_place
from .timeline_events import prefetch_timeline_events, resolve_event_date

logger = logging.getLogger(__name__)

# Ceiling on concurrent per-relative GET_PERSON date fetches, so a family with
# many children does not flood the shared httpx pool (MCP-22).
_MEMBER_FETCH_CONCURRENCY = 8


async def format_family_detail(client, tree_id: str, handle: str) -> str:
    """Format comprehensive family data with timeline and citations."""
    # Get family data
    family_data = await client.make_api_call(
        ApiCalls.GET_FAMILY, tree_id=tree_id, handle=handle, params={"extend": "all"}
    )

    # Get family timeline
    timeline_data = await client.make_api_call(
        ApiCalls.GET_FAMILY_TIMELINE,
        tree_id=tree_id,
        handle=handle,
        # No params needed for family timeline
    )

    result = "=== FAMILY DETAILS ===\n"

    # Extract basic info
    gramps_id = family_data.get("gramps_id", "")
    result += f"Family {gramps_id} - [{handle}]\n"

    # Parents section
    result += "\nPARENTS:\n"
    extended = family_data.get("extended", {})

    father = extended.get("father", {})
    mother = extended.get("mother", {})
    children = extended.get("children", [])

    # Fan out every member date fetch (father, mother, each child) concurrently
    # instead of one serial GET_PERSON per member (MCP-22). Results stay in
    # emission order, so consuming them with next() below is byte-identical to
    # the original serial output.
    members = [
        *([father] if father else []),
        *([mother] if mother else []),
        *children,
    ]
    member_dates = iter(
        await gather_bounded(
            _MEMBER_FETCH_CONCURRENCY,
            [_get_birth_death_dates(client, tree_id, m) for m in members],
        )
    )

    # Father
    if father:
        father_name = _extract_person_name(father)
        father_gender = _get_gender_letter(father.get("gender", 2))
        father_id = father.get("gramps_id", "")
        father_birth, father_death = next(member_dates)
        dates = ", ".join(filter(None, [father_birth, father_death]))
        result += f"Father: {father_name} ({father_gender}) - {father_id} - {dates}\n"

    # Mother
    if mother:
        mother_name = _extract_person_name(mother)
        mother_gender = _get_gender_letter(mother.get("gender", 2))
        mother_id = mother.get("gramps_id", "")
        mother_birth, mother_death = next(member_dates)
        dates = ", ".join(filter(None, [mother_birth, mother_death]))
        result += f"Mother: {mother_name} ({mother_gender}) - {mother_id} - {dates}\n"

    # Children section
    if children:
        result += "\nCHILDREN:\n"
        for child in children:
            child_name = _extract_person_name(child)
            child_gender = _get_gender_letter(child.get("gender", 2))
            child_id = child.get("gramps_id", "")
            child_birth, child_death = next(member_dates)
            dates = ", ".join(filter(None, [child_birth, child_death]))
            result += f"- {child_name} ({child_gender}) - {child_id} - {dates}\n"

    # Marriage information
    result += "\nMarried:\n"
    event_ref_list = family_data.get("event_ref_list", [])
    for event_ref in event_ref_list:
        event_handle = event_ref.get("ref", "")
        if event_handle:
            try:
                event_data = await client.make_api_call(
                    ApiCalls.GET_EVENT, tree_id=tree_id, handle=event_handle
                )
                event_type = event_data.get("type", "")
                if event_type.lower() in ["marriage", "married"]:
                    event_date = format_date(event_data.get("date", {}))
                    event_place = await format_place(
                        client, tree_id, event_data.get("place", ""), inline=True
                    )
                    result += f"{event_date} - {event_place}\n"
                    break
            except Exception as e:
                logger.warning(f"Failed to fetch event {event_handle}: {e}")
                continue

    # Timeline section
    result += "\nTIMELINE:\n"
    if timeline_data:
        # Pre-fetch every referenced event concurrently (bounded) instead of one
        # serial GET_EVENT per entry (MCP-22). Failures are captured in place and
        # handled per entry via resolve_event_date below.
        fetched_events = await prefetch_timeline_events(client, tree_id, timeline_data)

        for timeline_event in timeline_data:
            if not isinstance(timeline_event, dict):
                continue

            # Basic event info from timeline
            event_type = timeline_event.get("type", "Unknown")
            event_id = timeline_event.get("gramps_id", "")
            role = timeline_event.get("role", "Primary")
            event_handle = timeline_event.get("handle", "")

            # Get properly formatted date using format_date function
            event_data, event_date = resolve_event_date(
                fetched_events.get(event_handle),
                timeline_event,
                event_handle,
            )

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
                # For family timeline, we might have different relationships
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
                    logger.warning(f"Failed to fetch citations for event: {e}")

    # Attached media section (from family's extend=all data)
    result += "\nAttached media:\n"
    extended_media = extended.get("media", [])
    for media_obj in extended_media:
        if isinstance(media_obj, dict):
            media_desc = media_obj.get("desc", "")
            media_id = media_obj.get("gramps_id", "")
            result += f"- {media_desc} ({media_id})\n"

    # Attached notes section (from family's extend=all data)
    result += "\nAttached notes:\n"
    extended_notes = extended.get("notes", [])
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
    """Get birth and death dates with places for a person."""
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

        birth_info = ""
        death_info = ""

        # Check for birth event
        birth_ref_index = full_person_data.get("birth_ref_index", -1)
        if birth_ref_index >= 0 and birth_ref_index < len(events):
            birth_event = events[birth_ref_index]
            birth_date = format_date(birth_event.get("date", {}))
            birth_place = await format_place(
                client, tree_id, birth_event.get("place", ""), inline=True
            )
            birth_info = f"{birth_date} - {birth_place}" if birth_place else birth_date

        # Check for death event
        death_ref_index = full_person_data.get("death_ref_index", -1)
        if death_ref_index >= 0 and death_ref_index < len(events):
            death_event = events[death_ref_index]
            death_date = format_date(death_event.get("date", {}))
            death_place = await format_place(
                client, tree_id, death_event.get("place", ""), inline=True
            )
            death_info = f"{death_date} - {death_place}" if death_place else death_date

        # If still living, show as such
        if full_person_data.get("living", False):
            death_info = "Living"

        return birth_info, death_info

    except Exception as e:
        logger.warning(f"Failed to get birth/death dates for {person_handle}: {e}")
        return "", ""
