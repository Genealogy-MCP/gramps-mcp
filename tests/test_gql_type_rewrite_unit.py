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

BIRTH_MAP = {"Birth": 12, "Marriage": 1, "Immigration": 3, "Death": 13}


class TestEventRewrite:
    def test_quoted_double(self):
        assert (
            rewrite_type_filters('type.string = "Birth"', "events", BIRTH_MAP)
            == "type.value = 12"
        )

    def test_quoted_single(self):
        assert (
            rewrite_type_filters("type.string = 'Marriage'", "events", BIRTH_MAP)
            == "type.value = 1"
        )

    def test_unquoted(self):
        assert (
            rewrite_type_filters("type.string = Immigration", "events", BIRTH_MAP)
            == "type.value = 3"
        )

    def test_bare_type_spelling(self):
        assert (
            rewrite_type_filters("type = Birth", "events", BIRTH_MAP)
            == "type.value = 12"
        )

    def test_not_equal_preserved(self):
        assert (
            rewrite_type_filters('type.string != "Birth"', "events", BIRTH_MAP)
            == "type.value != 12"
        )

    def test_compound_query_rewrites_in_place(self):
        assert (
            rewrite_type_filters(
                'type.string = "Birth" and date.dateval[2] > 1850',
                "events",
                BIRTH_MAP,
            )
            == "type.value = 12 and date.dateval[2] > 1850"
        )


class TestPlaceRewrite:
    def test_place_type_string(self):
        assert (
            rewrite_type_filters('place_type.string = "City"', "places", {"City": 4})
            == "place_type.value = 4"
        )

    def test_bare_place_type(self):
        assert (
            rewrite_type_filters("place_type = City", "places", {"City": 4})
            == "place_type.value = 4"
        )


class TestFamilyAndRepositoryRewrite:
    def test_family_type(self):
        assert (
            rewrite_type_filters('type.string = "Married"', "families", {"Married": 0})
            == "type.value = 0"
        )

    def test_repository_type(self):
        assert (
            rewrite_type_filters(
                'type.string = "Archive"', "repositories", {"Archive": 2}
            )
            == "type.value = 2"
        )


class TestPassThrough:
    def test_type_value_untouched(self):
        assert (
            rewrite_type_filters("type.value = 12", "events", BIRTH_MAP)
            == "type.value = 12"
        )

    def test_unrelated_query_untouched(self):
        q = "date.dateval[2] > 1850 and gramps_id = E0541"
        assert rewrite_type_filters(q, "events", BIRTH_MAP) == q

    def test_unknown_name_untouched(self):
        # Custom names are handled in a later slice (#85); an unknown
        # default name passes through byte-for-byte.
        q = 'type.string = "LVG"'
        assert rewrite_type_filters(q, "events", BIRTH_MAP) == q

    def test_contains_operator_untouched(self):
        q = "type.string ~ Marr"
        assert rewrite_type_filters(q, "events", BIRTH_MAP) == q

    def test_place_type_not_matched_as_type(self):
        # The bare `type` pattern must not fire inside `place_type`.
        q = "place_type.string = City"
        assert rewrite_type_filters(q, "events", {"City": 4}) == q

    def test_entity_without_typed_enum_untouched(self):
        q = 'type.string = "Birth"'
        assert rewrite_type_filters(q, "people", BIRTH_MAP) == q


class TestNamesWithSpaces:
    def test_quoted_multiword_name(self):
        assert (
            rewrite_type_filters(
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
    assert rewrite_type_filters(query, "events", BIRTH_MAP) == query
