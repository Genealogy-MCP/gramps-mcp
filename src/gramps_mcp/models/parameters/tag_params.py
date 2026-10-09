# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""
Pydantic models for tag-related operations.

API calls supported in this category:
- GET_TAGS: Get information about multiple tags
- POST_TAGS: Add a new tag to the database
- GET_TAG: Get information about a specific tag
- PUT_TAG: Update the tag
- DELETE_TAG: Delete the tag
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class TagSearchParams(BaseModel):
    """Parameters for searching tags."""

    # Reason: extra="forbid" (#95), see BaseGetMultipleParams.
    model_config = {"extra": "forbid"}

    page: Optional[int] = Field(
        None, description="Page number for pagination (1-based)", ge=1
    )
    pagesize: Optional[int] = Field(
        None, description="Number of results per page", ge=1, le=100
    )
    sort: Optional[List[str]] = Field(None, description="Sort order for results")


class TagSaveParams(BaseModel):
    """Parameters for creating or updating a tag."""

    # Reason: the only write model not built on BaseDataModel, so it needs its
    # own copy of the #71 setting.
    model_config = {"extra": "forbid"}

    handle: Optional[str] = Field(
        None,
        description=(
            "Tag's handle. Pass it to update an existing tag via "
            "PUT /tags/{handle}; omit to create a new tag."
        ),
    )
    name: str = Field(description="Tag name", min_length=1)
    color: Optional[str] = Field(
        None, description="Tag color as a hex string, e.g. '#EF2929'"
    )
    priority: Optional[int] = Field(
        None, description="Tag priority; lower sorts first in Gramps"
    )
    change: Optional[str] = Field(None, description="Change timestamp")
