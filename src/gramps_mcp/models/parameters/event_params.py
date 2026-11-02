# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Pydantic models for event-related operations.

API calls supported in this category:
- GET_EVENTS: Get information about multiple events
- POST_EVENTS: Add a new event to the database
- GET_EVENT: Get information about a specific event
- PUT_EVENT: Update the event
- DELETE_EVENT: Delete the event
"""

from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from .base_params import (
    AttributeListField,
    BaseDataModel,
    BaseGetMultipleParams,
    MediaListField,
    NoteListField,
)


class EventSearchParams(BaseGetMultipleParams):
    """Parameters for searching multiple events."""

    dates: Optional[str] = Field(
        None, description="Date filter (y/m/d, -y/m/d, y/m/d-y/m/d, y/m/d-)"
    )


class EventSaveParams(BaseDataModel, NoteListField, AttributeListField, MediaListField):
    """Parameters for creating or updating an event."""

    type: Optional[str] = Field(
        None,
        description=(
            "Event type (Birth, Death, Marriage, etc.). "
            "Required when creating (no handle)."
        ),
    )
    date: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Event date object with dateval array [day, month, year, False], "
            "quality (0=regular, 1=estimated, 2=calculated), and modifier "
            "(0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, "
            "6=textonly, 7=from, 8=to)"
        ),
    )
    description: Optional[str] = Field(None, description="Event description")
    place: Optional[str] = Field(None, description="Place handle where event occurred")
    citation_list: Optional[List[str]] = Field(
        None,
        description=(
            "List of citation handles. Optional but recommended: attaching a "
            "source citation documents where this event's information came from."
        ),
    )

    @model_validator(mode="after")
    def _validate_create_required(self) -> "EventSaveParams":
        """Enforce required fields when creating (no handle = new entity)."""
        if self.handle is not None:
            return self
        missing = [f for f in ("type",) if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Required when creating: {', '.join(missing)}")
        return self
