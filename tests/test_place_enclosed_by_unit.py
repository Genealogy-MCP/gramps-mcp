# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the place enclosure parameter and its PUT merge policy.

Covers PlaceSaveParams.to_api_payload() translating enclosed_by into a
placeref_list entry, and merge_place_refs() keeping a place to a single
current parent while letting date-qualified historic enclosures accumulate.
"""

from src.gramps_mcp._merge import merge_place_refs
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams

# Reason: Gramps Web stores an empty Date object, not null, on an undated
# placeref. The merge policy must read that as "no date" (#67).
EMPTY_DATE = {
    "_class": "Date",
    "calendar": 0,
    "dateval": [0, 0, 0, False],
    "modifier": 0,
    "quality": 0,
    "sortval": 0,
    "text": "",
    "year": 0,
}
DATE_1800 = {"_class": "Date", "dateval": [0, 0, 1800, False], "text": ""}
DATE_1900 = {"_class": "Date", "dateval": [0, 0, 1900, False], "text": ""}


class TestEnclosedByPayload:
    """enclosed_by must reach the API as placeref_list."""

    def test_enclosed_by_becomes_placeref_list(self):
        """A create with enclosed_by emits the placeref_list Gramps stores."""
        payload = PlaceSaveParams(
            name={"value": "Boston"}, place_type="City", enclosed_by="parent_handle"
        ).to_api_payload()

        assert payload["placeref_list"] == [{"ref": "parent_handle"}]
        assert "enclosed_by" not in payload

    def test_enclosed_by_absent_leaves_placeref_list_unset(self):
        """Omitting enclosed_by must not invent an empty enclosure."""
        payload = PlaceSaveParams(
            name={"value": "United States"}, place_type="Country"
        ).to_api_payload()

        assert "placeref_list" not in payload
        assert "enclosed_by" not in payload

    def test_explicit_placeref_list_wins(self):
        """placeref_list takes precedence and enclosed_by is not merged in."""
        payload = PlaceSaveParams(
            handle="place_handle",
            enclosed_by="shorthand_handle",
            placeref_list=[{"ref": "explicit_handle", "date": DATE_1900}],
        ).to_api_payload()

        assert payload["placeref_list"] == [
            {"ref": "explicit_handle", "date": DATE_1900}
        ]
        assert "enclosed_by" not in payload

    def test_enclosed_by_on_update_survives_alt_names_wrapping(self):
        """The two translations in to_api_payload() do not interfere."""
        payload = PlaceSaveParams(
            handle="place_handle", enclosed_by="parent_handle", alt_names=["Beantown"]
        ).to_api_payload()

        assert payload["placeref_list"] == [{"ref": "parent_handle"}]
        assert payload["alt_names"] == [{"value": "Beantown"}]


class TestMergePlaceRefs:
    """A place keeps one current parent across merging PUTs."""

    def test_reparenting_replaces_the_stored_parent(self):
        """A new undated enclosure supersedes the stored undated one."""
        merged = merge_place_refs(
            [{"_class": "PlaceRef", "ref": "old_parent", "date": EMPTY_DATE}],
            [{"ref": "new_parent"}],
        )

        assert merged == [{"ref": "new_parent"}]

    def test_repeating_the_same_parent_is_idempotent(self):
        """Re-PUTting the same enclosure leaves exactly one entry."""
        merged = merge_place_refs(
            [{"_class": "PlaceRef", "ref": "parent", "date": EMPTY_DATE}],
            [{"ref": "parent"}],
        )

        assert merged == [{"ref": "parent"}]

    def test_first_enclosure_is_added(self):
        """A place with no stored parent gains the supplied one."""
        assert merge_place_refs([], [{"ref": "parent"}]) == [{"ref": "parent"}]

    def test_null_date_is_also_undated(self):
        """The documented "date": null form must merge like an empty Date."""
        merged = merge_place_refs(
            [{"ref": "old_parent", "date": None}], [{"ref": "new_parent"}]
        )

        assert merged == [{"ref": "new_parent"}]

    def test_dated_enclosures_accumulate(self):
        """Historic, date-qualified enclosures are additive, not singular."""
        stored = [{"ref": "old_parent", "date": DATE_1800}]
        merged = merge_place_refs(stored, [{"ref": "other_parent", "date": DATE_1900}])

        assert merged == [
            {"ref": "old_parent", "date": DATE_1800},
            {"ref": "other_parent", "date": DATE_1900},
        ]

    def test_dated_history_survives_reparenting(self):
        """Replacing the current parent keeps the dated enclosure record."""
        stored = [
            {"ref": "historic_parent", "date": DATE_1800},
            {"_class": "PlaceRef", "ref": "old_parent", "date": EMPTY_DATE},
        ]
        merged = merge_place_refs(stored, [{"ref": "new_parent"}])

        assert merged == [
            {"ref": "historic_parent", "date": DATE_1800},
            {"ref": "new_parent"},
        ]
