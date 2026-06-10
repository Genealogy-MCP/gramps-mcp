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
- GET_PERSON_DNA_MATCHES: Get DNA matches for a specific person
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from .base_params import BaseDataModel


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


class PersonData(BaseDataModel):
    """Model for creating or updating a person in Gramps API."""

    primary_name: Optional[Dict[str, Any]] = Field(
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
    alternate_names: Optional[List[Dict[str, Any]]] = Field(
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
            "On update: replaces the entire alternate_names list (not merged)"
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


class PersonDnaMatchesParams(BaseModel):
    """Parameters for getting DNA matches for a person from Gramps API."""

    raw: Optional[bool] = Field(None, description="Include raw data for the matches")
