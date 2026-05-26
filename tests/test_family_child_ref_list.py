# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Tests for FamilySaveParams.to_api_payload() child_handles translation."""

from src.gramps_mcp.models.parameters.family_params import FamilySaveParams


class TestFamilyChildRefListTranslation:
    """FamilySaveParams.to_api_payload() translates child_handles to child_ref_list."""

    def test_populated_child_handles_produces_child_ref_list(self) -> None:
        """Populated child_handles list produces child_ref_list with Birth defaults."""
        model = FamilySaveParams(child_handles=["h1", "h2"])
        result = model.to_api_payload()

        assert result["child_ref_list"] == [
            {
                "ref": "h1",
                "frel": {"_class": "ChildRefType", "string": "Birth"},
                "mrel": {"_class": "ChildRefType", "string": "Birth"},
            },
            {
                "ref": "h2",
                "frel": {"_class": "ChildRefType", "string": "Birth"},
                "mrel": {"_class": "ChildRefType", "string": "Birth"},
            },
        ]

    def test_none_child_handles_omits_child_ref_list(self) -> None:
        """child_handles=None does not emit child_ref_list in payload."""
        model = FamilySaveParams(father_handle="abc")
        result = model.to_api_payload()

        assert "child_ref_list" not in result
        assert "child_handles" not in result

    def test_empty_child_handles_emits_empty_child_ref_list(self) -> None:
        """child_handles=[] emits child_ref_list: [] in payload."""
        model = FamilySaveParams(child_handles=[])
        result = model.to_api_payload()

        assert result["child_ref_list"] == []
        assert "child_handles" not in result

    def test_child_handles_stripped_sibling_fields_preserved(self) -> None:
        """child_handles key is removed; father_handle and mother_handle survive."""
        model = FamilySaveParams(
            father_handle="dad1",
            mother_handle="mom1",
            child_handles=["kid1"],
        )
        result = model.to_api_payload()

        assert "child_handles" not in result
        assert result["father_handle"] == "dad1"
        assert result["mother_handle"] == "mom1"
        assert len(result["child_ref_list"]) == 1
