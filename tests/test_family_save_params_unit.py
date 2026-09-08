# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for the reshaped FamilySaveParams (#60, #62, #63, #64).

Covers the full child_ref objects param, the family-level citation_list, and
the family_type -> top-level `type` mapping in to_api_payload().
"""

from src.gramps_mcp.models.parameters.family_params import FamilySaveParams

BIRTH = "Birth"


class TestFamilyChildRefListParam:
    """FamilySaveParams accepts full child_ref objects (#60, #63)."""

    def test_child_ref_list_takes_precedence_over_child_handles(self) -> None:
        """child_ref_list wins when both it and child_handles are supplied."""
        model = FamilySaveParams(
            handle="fam1",
            child_handles=["ignored"],
            child_ref_list=[{"ref": "kid1", "citation_list": ["c1"]}],
        )
        result = model.to_api_payload()

        assert "child_handles" not in result
        assert result["child_ref_list"] == [{"ref": "kid1", "citation_list": ["c1"]}]

    def test_child_ref_list_on_update_omits_unset_relations(self) -> None:
        """On update, frel/mrel are not defaulted, so stored values stand."""
        model = FamilySaveParams(
            handle="fam1",
            child_ref_list=[{"ref": "kid1", "note_list": ["n1"], "private": True}],
        )
        result = model.to_api_payload()

        assert result["child_ref_list"] == [
            {"ref": "kid1", "note_list": ["n1"], "private": True}
        ]

    def test_child_ref_list_on_create_defaults_birth_relations(self) -> None:
        """On create (no handle) frel/mrel default to Birth, as child_handles does."""
        model = FamilySaveParams(child_ref_list=[{"ref": "kid1"}])
        result = model.to_api_payload()

        assert result["child_ref_list"] == [
            {"ref": "kid1", "frel": BIRTH, "mrel": BIRTH}
        ]

    def test_explicit_relations_are_sent_as_bare_names(self) -> None:
        """frel/mrel go out as bare name strings, the only form Gramps stores.

        A {"_class": "ChildRefType", "string": ...} dict is accepted by the API
        and then silently ignored, leaving the relationship at Birth (#60).
        """
        model = FamilySaveParams(
            handle="fam1",
            child_ref_list=[{"ref": "kid1", "frel": "Adopted", "mrel": "Birth"}],
        )
        result = model.to_api_payload()

        assert result["child_ref_list"] == [
            {"ref": "kid1", "frel": "Adopted", "mrel": BIRTH}
        ]

    def test_child_ref_list_requires_ref(self) -> None:
        """A child_ref entry without a ref handle is rejected loudly."""
        try:
            FamilySaveParams(child_ref_list=[{"citation_list": ["c1"]}])
        except Exception as exc:  # pydantic.ValidationError
            assert "ref" in str(exc)
        else:  # pragma: no cover - guard
            raise AssertionError("Expected validation to fail without 'ref'")


class TestFamilyLevelFields:
    """Family-level citation_list and family_type (#62, #64)."""

    def test_citation_list_passes_through(self) -> None:
        """Family-level citation_list reaches the payload unchanged."""
        model = FamilySaveParams(handle="fam1", citation_list=["c1", "c2"])
        result = model.to_api_payload()

        assert result["citation_list"] == ["c1", "c2"]

    def test_family_type_maps_to_top_level_type(self) -> None:
        """family_type is emitted as the top-level Gramps `type` string."""
        model = FamilySaveParams(handle="fam1", family_type="Married")
        result = model.to_api_payload()

        assert result["type"] == "Married"
        assert "family_type" not in result

    def test_family_type_absent_when_unset(self) -> None:
        """No family_type means no `type` key in the payload."""
        result = FamilySaveParams(handle="fam1").to_api_payload()

        assert "type" not in result
