# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Pydantic models for place-related operations.

API calls supported in this category:
- GET_PLACES: Get information about multiple places
- POST_PLACES: Add a new place to the database
- GET_PLACE: Get information about a specific place
- PUT_PLACE: Update the place
- DELETE_PLACE: Delete the place
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .base_params import BaseGetMultipleParams, BaseGetSingleParams


class PlaceSearchParams(BaseGetMultipleParams):
    """Parameters for searching places."""

    pass


class PlaceDetailsParams(BaseGetSingleParams):
    """Parameters for getting specific place details."""

    pass


class PlaceSaveParams(BaseModel):
    """Parameters for creating or updating a place."""

    handle: Optional[str] = Field(
        None, min_length=8, description="Place handle (for updates; omit for new place)"
    )
    gramps_id: Optional[str] = Field(
        None, description="Alternate user managed identifier"
    )
    name: Optional[dict] = Field(
        None, description="Place name object with 'value' field"
    )
    code: Optional[str] = Field(None, description="Place code")
    alt_loc: Optional[List[dict]] = Field(None, description="Alternative locations")
    place_type: Optional[str] = Field(
        None,
        description="Place type. Required when creating (no handle).",
    )

    @model_validator(mode="after")
    def _validate_create_required(self) -> "PlaceSaveParams":
        """Enforce required fields when creating (no handle = new entity)."""
        if self.handle is not None:
            return self
        missing = [f for f in ("place_type",) if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Required when creating: {', '.join(missing)}")
        return self

    placeref_list: Optional[List[dict]] = Field(
        None, description="List of place references"
    )
    alt_names: Optional[List[str]] = Field(None, description="Alternative names")
    lat: Optional[str] = Field(None, description="Latitude coordinate")
    long: Optional[str] = Field(None, description="Longitude coordinate")
    urls: Optional[List[dict]] = Field(None, description="Associated URLs")
    media_list: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of media references (e.g. [{'ref': 'handle'}])"
    )
    citation_list: Optional[List[str]] = Field(
        None, description="List of citation handles"
    )
    note_list: Optional[List[str]] = Field(None, description="List of note handles")
    tag_list: Optional[List[str]] = Field(None, description="List of tag handles")
    private: Optional[bool] = Field(None, description="Mark as private")
    list_mode: Optional[Literal["merge", "replace"]] = Field(
        default="merge",
        description=(
            'List field behavior on update: "merge" (default) appends '
            'with dedup, "replace" overwrites'
        ),
    )
