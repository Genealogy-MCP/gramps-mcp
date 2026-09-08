# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for child_ref_list merging (#60, #63).

A family holds at most one child_ref per child, so child_ref_list merges by
`ref` identity and merges the entry's nested lists, rather than appending a
second entry for the same child the way merge_ref_items would.
"""

from src.gramps_mcp._merge import merge_child_refs

BIRTH = {"_class": "ChildRefType", "string": "Birth"}
ADOPTED = {"_class": "ChildRefType", "string": "Adopted"}


class TestMergeChildRefs:
    """merge_child_refs keeps one entry per child and unions nested lists."""

    def test_citation_added_to_existing_child_ref(self):
        existing = [
            {
                "_class": "ChildRef",
                "ref": "kid1",
                "frel": BIRTH,
                "mrel": BIRTH,
                "citation_list": [],
                "note_list": [],
                "private": False,
            }
        ]
        new = [{"ref": "kid1", "citation_list": ["cit1"]}]

        result = merge_child_refs(existing, new)

        assert len(result) == 1
        assert result[0]["citation_list"] == ["cit1"]
        assert result[0]["frel"] == BIRTH

    def test_repeated_merge_is_idempotent(self):
        existing = [{"ref": "kid1", "citation_list": ["cit1"]}]
        new = [{"ref": "kid1", "citation_list": ["cit1"]}]

        assert merge_child_refs(existing, new) == [
            {"ref": "kid1", "citation_list": ["cit1"]}
        ]

    def test_new_child_is_appended(self):
        existing = [{"ref": "kid1", "frel": BIRTH, "mrel": BIRTH}]
        new = [{"ref": "kid2", "frel": BIRTH, "mrel": BIRTH}]

        result = merge_child_refs(existing, new)

        assert [entry["ref"] for entry in result] == ["kid1", "kid2"]

    def test_explicit_relation_overrides_stored_value(self):
        existing = [{"ref": "kid1", "frel": BIRTH, "mrel": BIRTH}]
        new = [{"ref": "kid1", "frel": ADOPTED}]

        result = merge_child_refs(existing, new)

        assert len(result) == 1
        assert result[0]["frel"] == ADOPTED
        assert result[0]["mrel"] == BIRTH

    def test_omitted_relation_preserves_stored_value(self):
        existing = [{"ref": "kid1", "frel": ADOPTED, "mrel": ADOPTED}]
        new = [{"ref": "kid1", "note_list": ["n1"]}]

        result = merge_child_refs(existing, new)

        assert result[0]["frel"] == ADOPTED
        assert result[0]["note_list"] == ["n1"]

    def test_existing_entries_without_ref_survive(self):
        existing = [{"unexpected": True}, {"ref": "kid1"}]
        new = [{"ref": "kid1", "citation_list": ["cit1"]}]

        result = merge_child_refs(existing, new)

        assert result[0] == {"unexpected": True}
        assert result[1]["citation_list"] == ["cit1"]
