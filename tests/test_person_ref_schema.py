# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for PersonData.person_ref_list schema (associations, issue #40)."""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.people_params import PersonData, PersonReference


class TestPersonReferenceSchema:
    """PersonReference submodel and PersonData.person_ref_list wiring."""

    def test_person_data_accepts_person_ref_list(self) -> None:
        model = PersonData(
            handle="p1",
            person_ref_list=[{"ref": "p2", "rel": "Cousin"}],
        )
        assert model.person_ref_list[0].ref == "p2"
        assert model.person_ref_list[0].rel == "Cousin"

    def test_rel_is_bare_string_and_optional_lists_omitted(self) -> None:
        model = PersonData(
            handle="p1",
            person_ref_list=[{"ref": "p2", "rel": "Godparent"}],
        )
        payload = model.to_api_payload()
        entry = payload["person_ref_list"][0]
        assert entry == {"ref": "p2", "rel": "Godparent"}
        assert "citation_list" not in entry
        assert "note_list" not in entry

    def test_optional_evidence_lists_retained_when_present(self) -> None:
        model = PersonData(
            handle="p1",
            person_ref_list=[
                {
                    "ref": "p2",
                    "rel": "Friend",
                    "citation_list": ["c1"],
                    "note_list": ["n1"],
                }
            ],
        )
        entry = model.to_api_payload()["person_ref_list"][0]
        assert entry["citation_list"] == ["c1"]
        assert entry["note_list"] == ["n1"]

    def test_missing_ref_raises(self) -> None:
        with pytest.raises(ValidationError):
            PersonReference(rel="Cousin")

    def test_missing_rel_raises(self) -> None:
        with pytest.raises(ValidationError):
            PersonReference(ref="p2")
