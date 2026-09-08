# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for the GQL typed-enum name rewrite (issue #84).

The Gramps GQL engine evaluates filters against Python objects where
``GrampsType`` has no ``.string`` attribute, so name comparisons like
``type.string = "Birth"`` silently match nothing. The rewrite translates
them to the working ``type.value = <int>`` form before the API call.
"""

import pytest

from src.gramps_mcp.tools._gql_type_rewrite import rewrite_type_filters


def rw(*args, **kwargs):
    """Shorthand: unwrap the rewritten query string for default-only cases."""
    return rewrite_type_filters(*args, **kwargs).gql


BIRTH_MAP = {"Birth": 12, "Marriage": 1, "Immigration": 3, "Death": 13}


class TestEventRewrite:
    def test_quoted_double(self):
        assert rw('type.string = "Birth"', "events", BIRTH_MAP) == "type.value = 12"

    def test_quoted_single(self):
        assert rw("type.string = 'Marriage'", "events", BIRTH_MAP) == "type.value = 1"

    def test_unquoted(self):
        assert rw("type.string = Immigration", "events", BIRTH_MAP) == "type.value = 3"

    def test_bare_type_spelling(self):
        assert rw("type = Birth", "events", BIRTH_MAP) == "type.value = 12"

    def test_not_equal_preserved(self):
        assert rw('type.string != "Birth"', "events", BIRTH_MAP) == "type.value != 12"

    def test_compound_query_rewrites_in_place(self):
        assert (
            rw(
                'type.string = "Birth" and date.dateval[2] > 1850',
                "events",
                BIRTH_MAP,
            )
            == "type.value = 12 and date.dateval[2] > 1850"
        )


class TestPlaceRewrite:
    def test_place_type_string(self):
        assert (
            rw('place_type.string = "City"', "places", {"City": 4})
            == "place_type.value = 4"
        )

    def test_bare_place_type(self):
        assert rw("place_type = City", "places", {"City": 4}) == "place_type.value = 4"


class TestFamilyAndRepositoryRewrite:
    def test_family_type(self):
        assert (
            rw('type.string = "Married"', "families", {"Married": 0})
            == "type.value = 0"
        )

    def test_repository_type(self):
        assert (
            rw('type.string = "Archive"', "repositories", {"Archive": 2})
            == "type.value = 2"
        )


class TestPassThrough:
    def test_type_value_untouched(self):
        assert rw("type.value = 12", "events", BIRTH_MAP) == "type.value = 12"

    def test_unrelated_query_untouched(self):
        q = "date.dateval[2] > 1850 and gramps_id = E0541"
        assert rw(q, "events", BIRTH_MAP) == q

    def test_unknown_name_untouched(self):
        # Custom names are handled in a later slice (#85); an unknown
        # default name passes through byte-for-byte.
        q = 'type.string = "LVG"'
        assert rw(q, "events", BIRTH_MAP) == q

    def test_contains_operator_untouched(self):
        q = "type.string ~ Marr"
        assert rw(q, "events", BIRTH_MAP) == q

    def test_place_type_not_matched_as_type(self):
        # The bare `type` pattern must not fire inside `place_type`.
        q = "place_type.string = City"
        assert rw(q, "events", {"City": 4}) == q

    def test_entity_without_typed_enum_untouched(self):
        q = 'type.string = "Birth"'
        assert rw(q, "people", BIRTH_MAP) == q


class TestNamesWithSpaces:
    def test_quoted_multiword_name(self):
        assert (
            rw(
                'type.string = "Marriage Banns"',
                "events",
                {"Marriage Banns": 7},
            )
            == "type.value = 7"
        )


@pytest.mark.parametrize(
    "query",
    ["", "   ", "private", "note_list.length > 0"],
)
def test_trivial_queries_pass_through(query):
    assert rw(query, "events", BIRTH_MAP) == query


class TestCustomNames:
    """Custom type names rewrite to a Custom-value pre-filter plus a
    client-side post filter on the API's returned type string (issue #85)."""

    CUSTOM = frozenset({"LVG", "Cattle Brand"})
    MAP = {**BIRTH_MAP, "Custom": 0}

    def test_custom_equality_prefilter_and_postfilter(self):
        result = rewrite_type_filters(
            'type.string = "LVG"', "events", self.MAP, custom_names=self.CUSTOM
        )
        assert result.gql == "type.value = 0"
        assert [(pf.field, pf.name) for pf in result.post_filters] == [("type", "LVG")]

    def test_custom_unquoted(self):
        result = rewrite_type_filters(
            "type = LVG", "events", self.MAP, custom_names=self.CUSTOM
        )
        assert result.gql == "type.value = 0"
        assert result.post_filters[0].name == "LVG"

    def test_custom_multiword(self):
        result = rewrite_type_filters(
            'type.string = "Cattle Brand"',
            "events",
            self.MAP,
            custom_names=self.CUSTOM,
        )
        assert result.gql == "type.value = 0"
        assert result.post_filters[0].name == "Cattle Brand"

    def test_default_name_yields_no_postfilter(self):
        result = rewrite_type_filters(
            'type.string = "Birth"', "events", self.MAP, custom_names=self.CUSTOM
        )
        assert result.gql == "type.value = 12"
        assert result.post_filters == ()

    def test_custom_in_and_compound(self):
        result = rewrite_type_filters(
            'type.string = "LVG" and date.dateval[2] > 1900',
            "events",
            self.MAP,
            custom_names=self.CUSTOM,
        )
        assert result.gql == "type.value = 0 and date.dateval[2] > 1900"
        assert result.post_filters[0].name == "LVG"

    def test_custom_not_equal_raises(self):
        from src.gramps_mcp.tools._errors import McpToolError

        with pytest.raises(McpToolError, match="!="):
            rewrite_type_filters(
                'type.string != "LVG"', "events", self.MAP, custom_names=self.CUSTOM
            )

    def test_custom_with_or_raises(self):
        from src.gramps_mcp.tools._errors import McpToolError

        with pytest.raises(McpToolError, match="or"):
            rewrite_type_filters(
                'type.string = "LVG" or private',
                "events",
                self.MAP,
                custom_names=self.CUSTOM,
            )

    def test_unknown_name_raises_actionable(self):
        from src.gramps_mcp.tools._errors import McpToolError

        with pytest.raises(McpToolError, match="LVG"):
            # Message lists the known names so the caller can self-correct.
            rewrite_type_filters(
                'type.string = "Bogus"', "events", self.MAP, custom_names=self.CUSTOM
            )

    def test_unknown_name_passes_through_without_custom_list(self):
        # custom_names=None means the custom list could not be fetched;
        # fall back to the pre-#85 passthrough instead of a hard error.
        q = 'type.string = "Bogus"'
        assert rw(q, "events", self.MAP, custom_names=None) == q


class TestMatchesPostFilters:
    def test_string_type_matches(self):
        from src.gramps_mcp.tools._gql_type_rewrite import (
            PostFilter,
            matches_post_filters,
        )

        pf = (PostFilter(field="type", name="LVG"),)
        assert matches_post_filters({"type": "LVG"}, pf)
        assert not matches_post_filters({"type": "Birth"}, pf)

    def test_dict_type_matches(self):
        from src.gramps_mcp.tools._gql_type_rewrite import (
            PostFilter,
            matches_post_filters,
        )

        pf = (PostFilter(field="type", name="LVG"),)
        assert matches_post_filters(
            {"type": {"_class": "EventType", "string": "LVG"}}, pf
        )
        assert not matches_post_filters({"type": {"string": "Birth"}}, pf)

    def test_missing_field_no_match(self):
        from src.gramps_mcp.tools._gql_type_rewrite import (
            PostFilter,
            matches_post_filters,
        )

        pf = (PostFilter(field="place_type", name="Church"),)
        assert not matches_post_filters({}, pf)

    def test_empty_filters_match_everything(self):
        from src.gramps_mcp.tools._gql_type_rewrite import matches_post_filters

        assert matches_post_filters({"type": "Birth"}, ())
