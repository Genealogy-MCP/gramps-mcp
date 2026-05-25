# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""Pydantic models for note-related operations.

API calls supported in this category:
- GET_NOTES: Get information about multiple notes
- POST_NOTES: Add a new note to the database
- GET_NOTE: Get information about a specific note
- PUT_NOTE: Update the note
- DELETE_NOTE: Delete the note
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from .base_params import BaseGetMultipleParams, BaseGetSingleParams


class NotesParams(BaseGetMultipleParams):
    """Parameters for getting information about multiple notes."""

    formats: str | None = Field(
        None,
        description="Comma delimited list of formats to apply (html)",
    )
    format_options: str | None = Field(
        None,
        description="JSON dictionary of options for note formatters",
    )


class NoteParams(BaseGetSingleParams):
    """Parameters for getting information about a specific note."""

    formats: str | None = Field(
        None,
        description="Comma delimited list of formats to apply (html)",
    )
    format_options: str | None = Field(
        None,
        description="JSON dictionary of options for note formatters",
    )


class NoteSaveParams(BaseModel):
    """Parameters for creating or updating a note."""

    handle: str | None = Field(
        None,
        description="Note's handle (for updates; omit for new note)",
    )
    text: str | None = Field(
        None, description="Note text content. Required when creating (no handle)."
    )
    type: str | None = Field(
        None, description="The type of note. Required when creating (no handle)."
    )

    @model_validator(mode="after")
    def _validate_create_required(self) -> "NoteSaveParams":
        """Enforce required fields when creating (no handle = new entity)."""
        if self.handle is not None:
            return self
        missing = [f for f in ("text", "type") if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Required when creating: {', '.join(missing)}")
        return self

    def to_api_payload(self) -> dict[str, Any]:
        """Return API-ready dict with text wrapped in StyledText format."""
        data = self.model_dump(exclude_none=True)
        if "text" in data and isinstance(data["text"], str):
            data["text"] = {
                "_class": "StyledText",
                "string": data["text"],
            }
        return data
