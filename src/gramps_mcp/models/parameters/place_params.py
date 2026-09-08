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

from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from .base_params import BaseDataModel, BaseGetMultipleParams, BaseGetSingleParams


class PlaceSearchParams(BaseGetMultipleParams):
    """Parameters for searching places."""

    pass


class PlaceDetailsParams(BaseGetSingleParams):
    """Parameters for getting specific place details."""

    pass


class PlaceSaveParams(BaseDataModel):
    """Parameters for creating or updating a place."""

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

    enclosed_by: Optional[str] = Field(
        None,
        description=(
            "Handle of the place that encloses this one, e.g. the state a "
            "city sits in. Written to placeref_list. On update it replaces "
            "the current enclosing place rather than adding a second parent. "
            "Ignored when placeref_list is supplied."
        ),
    )
    placeref_list: Optional[List[dict]] = Field(
        None,
        description=(
            "Full enclosure references, each {'ref': <place handle>} with an "
            "optional 'date' for a historic enclosure. Use enclosed_by for "
            "the ordinary single-parent case; this field takes precedence."
        ),
    )
    alt_names: Optional[List[str]] = Field(None, description="Alternative names")
    lat: Optional[str] = Field(None, description="Latitude coordinate")
    long: Optional[str] = Field(None, description="Longitude coordinate")
    urls: Optional[List[dict]] = Field(None, description="Associated URLs")
    citation_list: Optional[List[str]] = Field(
        None, description="List of citation handles"
    )

    def to_api_payload(self) -> Dict[str, Any]:
        """Build the Gramps place payload from the caller's parameters.

        Wraps alt_names as PlaceName objects and turns the enclosed_by
        shorthand into the placeref_list entry Gramps actually stores.

        Returns:
            Dict[str, Any]: The API-ready request body.
        """
        data = super().to_api_payload()
        alt_names = data.get("alt_names")
        if alt_names is not None:
            data["alt_names"] = [{"value": n} for n in alt_names]

        # Reason: enclosed_by is the guide's name for the enclosure and has no
        # Gramps counterpart; without this translation it was dropped and the
        # place was stored with an empty placeref_list (#67).
        enclosed_by = data.pop("enclosed_by", None)
        if enclosed_by is not None and data.get("placeref_list") is None:
            data["placeref_list"] = [{"ref": enclosed_by}]
        return data
