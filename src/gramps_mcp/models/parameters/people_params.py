# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Pydantic models for people-related operations.

API calls supported in this category:
- GET_PEOPLE: Get information about multiple people
- POST_PEOPLE: Add a new person to the database
- GET_PERSON: Get information about a specific person
- PUT_PERSON: Update the person
- DELETE_PERSON: Delete the person
- GET_PERSON_TIMELINE: Get the timeline for a specific person
"""

import difflib
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from .base_params import (
    AttributeListField,
    BaseDataModel,
    MediaListField,
    NoteListField,
)


class EventReference(BaseModel):
    """Model for event references in a person's event_ref_list."""

    ref: str = Field(..., description="The handle of the event referenced")
    role: str = Field(..., description="Role of the person in the event")


class PersonReference(BaseModel):
    """Model for an association in a person's person_ref_list.

    A non-parent/child/spouse link to another person (e.g. cousin, godparent).
    """

    ref: str = Field(..., description="The handle of the associated person")
    rel: str = Field(
        ...,
        description=(
            "Relationship descriptor (free text), e.g. 'Cousin', 'Godparent', 'Friend'"
        ),
    )
    citation_list: Optional[List[str]] = Field(
        None, description="Handles of citations evidencing the association"
    )
    note_list: Optional[List[str]] = Field(
        None, description="Handles of notes annotating the association"
    )


class PersonName(BaseModel):
    """Model for a Gramps Name: a person's primary_name or one alternate name."""

    # Reason: extra="forbid" (#113). Gramps Web POST stores an unknown Name
    # key as is (a bare "surname" next to first_name), and every later PUT of
    # that person then fails with HTTP 400 "unknown Name keys". The key has to
    # be rejected before the record is created.
    model_config = {
        "extra": "forbid",
        "populate_by_name": True,
        "serialize_by_alias": True,
    }

    class_: Optional[str] = Field(
        None, alias="_class", description="Gramps class tag, always 'Name'"
    )
    first_name: Optional[str] = Field(None, description="Given name(s)")
    surname_list: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "Surnames, each an object such as "
            '{"surname": "Smith", "primary": true}. A name has no bare '
            "surname key; the surname always goes here."
        ),
    )
    type: Optional[Any] = Field(
        None, description="Name type, e.g. 'Birth Name', 'Also Known As'"
    )
    suffix: Optional[str] = Field(None, description="Suffix, e.g. 'Jr.'")
    title: Optional[str] = Field(None, description="Title, e.g. 'Dr.'")
    nick: Optional[str] = Field(None, description="Nickname")
    call: Optional[str] = Field(None, description="Call name: the given name used")
    famnick: Optional[str] = Field(None, description="Family nickname")
    group_as: Optional[str] = Field(None, description="Surname to group under")
    sort_as: Optional[int] = Field(None, description="Name sort format number")
    display_as: Optional[int] = Field(None, description="Name display format number")
    date: Optional[Dict[str, Any]] = Field(
        None, description="Date object for when the name was used"
    )
    citation_list: Optional[List[str]] = Field(
        None, description="Handles of citations evidencing the name"
    )
    note_list: Optional[List[str]] = Field(None, description="Handles of notes")
    private: Optional[bool] = Field(None, description="Whether the name is private")

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_keys(cls, data: Any) -> Any:
        """Reject keys outside the Gramps Name schema with a corrective hint."""
        if not isinstance(data, dict):
            return data
        known = sorted(f.alias or name for name, f in cls.model_fields.items())
        unknown = [key for key in data if key not in known]
        if not unknown:
            return data
        parts = []
        for key in unknown:
            close = difflib.get_close_matches(key, known, n=1, cutoff=0.6)
            parts.append(
                f"'{key}' (did you mean '{close[0]}'?)" if close else f"'{key}'"
            )
        hint = ""
        if "surname" in unknown:
            entry = json.dumps({"surname": data["surname"]})
            hint = f" A surname goes in surname_list: [{entry}]."
        raise ValueError(
            f"Unknown Name key(s): {', '.join(parts)}.{hint} "
            f"Accepted Name keys: {', '.join(known)}."
        )


class PersonData(BaseDataModel, NoteListField, AttributeListField, MediaListField):
    """Model for creating or updating a person in Gramps API."""

    primary_name: Optional[PersonName] = Field(
        None,
        description=(
            "Person's primary name object with first_name and surname_list. "
            "Required when creating (no handle)."
        ),
    )
    gender: Optional[int] = Field(
        None,
        ge=0,
        le=2,
        description=(
            "Gender (0=Female, 1=Male, 2=Unknown). Required when creating (no handle)."
        ),
    )

    @model_validator(mode="after")
    def _validate_create_required(self) -> "PersonData":
        """Enforce required fields when creating (no handle = new entity)."""
        if self.handle is not None:
            return self
        missing = [f for f in ("primary_name", "gender") if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Required when creating: {', '.join(missing)}")
        return self

    event_ref_list: Optional[List[EventReference]] = Field(
        None, description="List of references to events the person participated in"
    )
    family_list: Optional[List[str]] = Field(
        None, description="List of handles for families the person was a parent of"
    )
    parent_family_list: Optional[List[str]] = Field(
        None, description="List of handles for families of the person's parents"
    )
    alternate_names: Optional[List[PersonName]] = Field(
        None,
        description=(
            "List of alternate name objects. "
            "Supported fields: first_name, surname_list, "
            "type (e.g. 'Also Known As', 'Married Name'), "
            "suffix, title, nick, call, famnick, "
            "citation_list (list of citation handles evidencing the name), "
            "note_list (list of note handles), "
            "date (Date object for when the name was used). "
            "Example with citation: "
            '{"first_name": "Maria", '
            '"surname_list": [{"surname": "Garcia"}], '
            '"type": "Married Name", '
            '"citation_list": ["<citation_handle>"]}. '
            "On update: merged with the stored list by default; "
            "pass list_mode='replace' to overwrite (#82)"
        ),
    )
    citation_list: Optional[List[str]] = Field(
        None,
        description=(
            "List of citation handles evidencing the person record itself "
            "(identity, not a single event). Optional but recommended: it "
            "records where the information about this person came from. On "
            'update the list_mode applies: "merge" (default) appends with '
            'dedup, "replace" overwrites the whole list.'
        ),
    )
    urls: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of URLs associated with the person"
    )
    person_ref_list: Optional[List[PersonReference]] = Field(
        None,
        description=(
            "List of associations: non-parent/child/spouse links to other "
            "people (e.g. cousins, godparents). Each entry is "
            '{"ref": "<person handle>", "rel": "<free-text descriptor>", '
            '"citation_list": [...], "note_list": [...]}. "rel" is a bare '
            "string (e.g. 'Cousin', 'Godparent', 'Friend'). On update the "
            'list_mode applies: "merge" (default) appends-with-dedup, '
            '"replace" overwrites the whole list.'
        ),
    )
    address_list: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "List of postal addresses where the person lived. Each entry "
            "accepts street, locality, city, county, state, country, postal, "
            "phone, date, citation_list, note_list, private. On update the "
            'list_mode applies: "merge" (default) appends with dedup, '
            '"replace" overwrites the whole list.'
        ),
    )
    lds_ord_list: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "List of LDS ordinances for the person. Each entry accepts type, "
            "date, temple, place, status, famc, citation_list, note_list, "
            "private. Unlike every other typed enum in this API, type and "
            "status must be integers here; passing the name string (e.g. "
            '"Baptism") makes the server reject it with HTTP 400. On update the '
            'list_mode applies: "merge" (default) appends with dedup, '
            '"replace" overwrites the whole list.'
        ),
    )


class PersonTimelineParams(BaseModel):
    """Parameters for getting a person's timeline from Gramps API."""

    dates: Optional[str] = Field(
        None,
        description=(
            "Date range to bound the timeline (e.g., -y/m/d, y/m/d-y/m/d, y/m/d-)"
        ),
    )
    first: Optional[bool] = Field(
        None, description="Discard events dated prior to the first event for the person"
    )
    last: Optional[bool] = Field(
        None, description="Discard events dated after the last event for the person"
    )
    ancestors: Optional[int] = Field(
        None, ge=0, description="Number of generations of ancestors to consider"
    )
    offspring: Optional[int] = Field(
        None, ge=0, description="Number of generations of offspring to consider"
    )
    events: Optional[str] = Field(
        None, description="Comma delimited list of specific events to include"
    )
    event_classes: Optional[str] = Field(
        None, description="Comma delimited list of event classes to include"
    )
    relatives: Optional[str] = Field(
        None, description="Comma delimited list of relationship types to consider"
    )
    relative_events: Optional[str] = Field(
        None, description="Comma delimited list of events for relatives"
    )
    relative_event_classes: Optional[str] = Field(
        None, description="Comma delimited list of event classes for relatives"
    )
    ratings: Optional[bool] = Field(
        None, description="Include citation count and highest confidence score"
    )
    precision: Optional[int] = Field(
        None,
        ge=1,
        le=3,
        description="Number of significant levels for date representation",
    )
    discard_empty: Optional[bool] = Field(None, description="Discard undated events")
    omit_anchor: Optional[bool] = Field(
        None, description="Omit person info for events pertaining to that person"
    )
    page: Optional[int] = Field(
        None, ge=1, description="Page number for pagination (1-based)"
    )
    pagesize: Optional[int] = Field(None, ge=1, description="Number of items per page")
