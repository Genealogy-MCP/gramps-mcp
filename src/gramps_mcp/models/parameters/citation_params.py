# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""
Pydantic models for citation-related operations.

API calls supported in this category:
- GET_CITATIONS: Get information about multiple citations
- POST_CITATIONS: Add a new citation to the database
- GET_CITATION: Get information about a specific citation
- PUT_CITATION: Update the citation
- DELETE_CITATION: Delete the citation
"""

from typing import Any, Dict, Optional

from pydantic import Field, model_validator

from .base_params import BaseDataModel, BaseGetMultipleParams


class GetCitationsParams(BaseGetMultipleParams):
    """Parameters for GET /citations endpoint."""

    dates: Optional[str] = Field(
        None, description="A date filter that operates on the citation date."
    )


class CitationData(BaseDataModel):
    """Model for creating or updating a citation via POST/PUT endpoints."""

    date: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Date object with dateval array [day, month, year, False], "
            "quality (0=regular, 1=estimated, 2=calculated), and modifier "
            "(0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, "
            "6=textonly, 7=from, 8=to)"
        ),
    )
    page: Optional[str] = Field(None, description="Page or location within the source")
    source_handle: Optional[str] = Field(
        None,
        description=(
            "Handle of the source being cited. Required when creating (no handle)."
        ),
    )

    @model_validator(mode="after")
    def _validate_create_required(self) -> "CitationData":
        """Enforce required fields when creating (no handle = new entity)."""
        if self.handle is not None:
            return self
        missing = [f for f in ("source_handle",) if getattr(self, f) is None]
        if missing:
            raise ValueError(f"Required when creating: {', '.join(missing)}")
        return self
