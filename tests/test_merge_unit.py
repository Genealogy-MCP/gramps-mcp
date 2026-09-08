# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests pinning the _merge normalizer against real Gramps GET payload shapes.

Issue #82: non-_list collection fields (alt_names, urls, alternate_names,
alt_loc) merge via merge_ref_items, whose dedup key comes from
_normalize_ref_item. The GET side returns entries enriched (_class, null/empty
defaults) while the PUT payload is minimal; both forms must normalize equal or
every re-PUT appends a duplicate.
"""

from src.gramps_mcp._merge import _normalize_ref_item, merge_ref_items


class TestNormalizeRefItem:
    """Pin the normalizer's stripping rules on real GET payload shapes."""

    def test_strips_class_key(self):
        assert _normalize_ref_item({"_class": "PlaceName", "value": "Neapolis"}) == {
            "value": "Neapolis"
        }

    def test_enriched_placename_equals_minimal_payload(self):
        # Stored form returned by GET places/{handle}
        enriched = {
            "_class": "PlaceName",
            "value": "Neapolis",
            "date": None,
            "lang": "",
        }
        minimal = {"value": "Neapolis"}
        assert _normalize_ref_item(enriched) == _normalize_ref_item(minimal)

    def test_enriched_url_equals_minimal_payload(self):
        enriched = {
            "_class": "Url",
            "type": {"_class": "UrlType", "string": "Web Home"},
            "path": "https://example.org",
            "desc": "",
            "private": False,
        }
        minimal = {"type": "Web Home", "path": "https://example.org"}
        assert _normalize_ref_item(enriched) == _normalize_ref_item(minimal)

    def test_enriched_empty_date_equals_absent_date(self):
        # GET expands an unset date into a full empty Date object; the minimal
        # payload omits it entirely. Both must normalize equal (#82).
        enriched = {
            "value": "Neapolis",
            "lang": "",
            "date": {
                "calendar": 0,
                "dateval": [0, 0, 0, False],
                "format": None,
                "modifier": 0,
                "newyear": 0,
                "quality": 0,
                "sortval": 0,
                "text": "",
                "year": 0,
            },
        }
        minimal = {"value": "Neapolis"}
        assert _normalize_ref_item(enriched) == _normalize_ref_item(minimal)

    def test_real_date_survives_normalization(self):
        item = {
            "value": "Neapolis",
            "date": {"dateval": [1, 1, 1900, False], "sortval": 2415021},
        }
        assert "date" in _normalize_ref_item(item)

    def test_real_date_with_and_without_sortval_key_equal(self):
        # sortval is computed server-side; the PUT payload omits it. A dated
        # entry must still dedup against its stored form (#82).
        enriched = {
            "value": "Neapolis",
            "date": {"dateval": [1, 1, 1900, False], "sortval": 2415021},
        }
        minimal = {"value": "Neapolis", "date": {"dateval": [1, 1, 1900, False]}}
        assert _normalize_ref_item(enriched) == _normalize_ref_item(minimal)

    def test_distinct_real_dates_stay_distinct(self):
        a = {"value": "Neapolis", "date": {"dateval": [1, 1, 1900, False]}}
        b = {"value": "Neapolis", "date": {"dateval": [2, 1, 1900, False]}}
        assert _normalize_ref_item(a) != _normalize_ref_item(b)

    def test_differing_desc_stays_distinct(self):
        # Full-identity dedup: same path, different desc = two entries.
        a = {"path": "https://example.org", "desc": "Parish register"}
        b = {"path": "https://example.org"}
        assert _normalize_ref_item(a) != _normalize_ref_item(b)


class TestMergeRefItemsWithoutRef:
    """merge_ref_items is now the fallback for all dict lists, ref or not."""

    def test_identical_reput_of_alt_name_dedups(self):
        existing = [
            {"_class": "PlaceName", "value": "Neapolis", "date": None, "lang": ""}
        ]
        new = [{"value": "Neapolis"}]
        assert merge_ref_items(existing, new) == existing

    def test_new_alt_name_appends(self):
        existing = [
            {"_class": "PlaceName", "value": "Neapolis", "date": None, "lang": ""}
        ]
        new = [{"value": "Parthenope"}]
        assert merge_ref_items(existing, new) == existing + new

    def test_identical_reput_of_url_dedups(self):
        existing = [
            {
                "_class": "Url",
                "type": {"_class": "UrlType", "string": "Web Home"},
                "path": "https://example.org",
                "desc": "",
                "private": False,
            }
        ]
        new = [{"type": "Web Home", "path": "https://example.org"}]
        assert merge_ref_items(existing, new) == existing
