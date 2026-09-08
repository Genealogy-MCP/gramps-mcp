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

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base_params import BaseDataModel

# Reason: Gramps Web resolves a typed enum from the bare name string. A
# {"_class": ..., "string": ...} dict is accepted but silently ignored and the
# field falls back to its default, which is how #60 lost adopted edges.
_BIRTH_REL = "Birth"


class ChildRefParams(BaseModel):
    """One parent-child edge of a family, with its own evidence.

    Gramps records evidence for the parent-child relationship itself on the
    child_ref, separately from the family's own citations: a birth act naming
    both parents is direct evidence of this edge, not of the marriage.
    """

    ref: str = Field(min_length=1, description="Handle of the child person")
    frel: Optional[str] = Field(
        None,
        description=(
            "Child's relationship to the father: Birth, Adopted, Stepchild, "
            "Sponsored, Foster, or Unknown. Defaults to Birth on create; "
            "omit on update to keep the stored value."
        ),
    )
    mrel: Optional[str] = Field(
        None,
        description=(
            "Child's relationship to the mother: Birth, Adopted, Stepchild, "
            "Sponsored, Foster, or Unknown. Defaults to Birth on create; "
            "omit on update to keep the stored value."
        ),
    )
    citation_list: Optional[List[str]] = Field(
        None,
        description="Handles of citations evidencing this parent-child edge",
    )
    note_list: Optional[List[str]] = Field(
        None, description="Handles of notes attached to this parent-child edge"
    )
    private: Optional[bool] = Field(
        None, description="Whether this parent-child edge is private"
    )


class FamilySaveParams(BaseDataModel):
    """Parameters for creating or updating a family."""

    father_handle: Optional[str] = Field(None, description="Father's handle")
    mother_handle: Optional[str] = Field(None, description="Mother's handle")
    child_handles: Optional[List[str]] = Field(
        None,
        description=(
            "Handles of the family's children, each added as a Birth edge. "
            "Shorthand for child_ref_list; ignored when child_ref_list is given."
        ),
    )
    child_ref_list: Optional[List[ChildRefParams]] = Field(
        None,
        description=(
            "Full parent-child edges, each carrying its own citations, notes "
            "and father/mother relationship. Takes precedence over "
            "child_handles. On update, an entry for a child already in the "
            "family updates that edge instead of adding a second one."
        ),
    )
    citation_list: Optional[List[str]] = Field(
        None,
        description=(
            "Handles of citations evidencing family-wide facts such as the "
            "marriage. Per-child evidence belongs on child_ref_list instead."
        ),
    )
    family_type: Optional[str] = Field(
        None,
        description=(
            "Relationship type of the couple: Married, Unmarried, "
            "Civil Union, Unknown, or a custom type defined in the tree."
        ),
    )
    event_ref_list: Optional[List[dict]] = Field(
        None, description="List of event references"
    )
    urls: Optional[List[dict]] = Field(
        None, description="List of URLs associated with the family"
    )

    def to_api_payload(self) -> Dict[str, Any]:
        """Build the Gramps family payload from the caller's parameters."""
        payload = super().to_api_payload()

        family_type = payload.pop("family_type", None)
        if family_type is not None:
            payload["type"] = family_type

        child_refs = payload.pop("child_ref_list", None)
        handles = payload.pop("child_handles", None)
        if child_refs is not None:
            payload["child_ref_list"] = [self._child_ref(ref) for ref in child_refs]
        elif handles is not None:
            payload["child_ref_list"] = [
                {"ref": h, "frel": _BIRTH_REL, "mrel": _BIRTH_REL} for h in handles
            ]
        return payload

    def _child_ref(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Fill in the Birth relationship defaults a newly created edge needs.

        Args:
            entry (Dict[str, Any]): One dumped ChildRefParams, None fields gone.

        Returns:
            Dict[str, Any]: The entry, with frel/mrel defaulted on create only.
        """
        # Reason: a create has no stored edge to preserve, so it needs the
        # Birth default child_handles always supplied. An update that omits
        # frel/mrel means "leave it alone", so defaulting there would quietly
        # demote an adopted child to a birth child (#60).
        if self.handle is not None:
            return dict(entry)
        return {"frel": _BIRTH_REL, "mrel": _BIRTH_REL, **entry}


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
