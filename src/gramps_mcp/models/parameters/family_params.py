# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Pydantic models for family-related operations.

API calls supported in this category:
- GET_FAMILIES: Get information about multiple families
- POST_FAMILIES: Add a new family to the database
- GET_FAMILY: Get information about a specific family
- PUT_FAMILY: Update the family
- DELETE_FAMILY: Delete the family
- GET_FAMILY_TIMELINE: Get the timeline for all the people in a specific family
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from .base_params import BaseDataModel


class FamilySaveParams(BaseDataModel):
    """Parameters for creating or updating a family."""

    father_handle: Optional[str] = Field(None, description="Father's handle")
    mother_handle: Optional[str] = Field(None, description="Mother's handle")
    child_handles: Optional[List[str]] = Field(
        None, description="List of child handles"
    )
    event_ref_list: Optional[List[dict]] = Field(
        None, description="List of event references"
    )
    urls: Optional[List[dict]] = Field(
        None, description="List of URLs associated with the family"
    )


class FamilyTimelineParams(BaseModel):
    """Parameters for getting family timeline information."""

    handle: str = Field(min_length=8, description="The unique identifier for a family")
    dates: Optional[str] = Field(None, description="Date range to bound the timeline")
    events: Optional[str] = Field(
        None, description="Comma delimited list of specific events"
    )
    event_classes: Optional[str] = Field(
        None, description="Comma delimited list of event classes"
    )
    ratings: Optional[bool] = Field(
        None, description="Include citation count and highest confidence score"
    )
    discard_empty: Optional[bool] = Field(None, description="Discard undated events")
    page: Optional[int] = Field(
        None, ge=1, description="Page number for pagination (1-based)"
    )
    pagesize: Optional[int] = Field(None, ge=1, description="Number of items per page")
