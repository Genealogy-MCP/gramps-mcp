# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for Name key validation on PersonData (#113).

A stray key in primary_name or alternate_names (most often a bare "surname")
used to reach Gramps Web unchanged. POST stored it, and every later PUT of the
person failed with HTTP 400 "unknown Name keys". PersonName now rejects any
key outside the Gramps Name schema before the call is made.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.people_params import PersonData, PersonName
from src.gramps_mcp.tools._errors import describe_validation_error

GRAMPS_NAME_KEYS = {
    "_class",
    "call",
    "citation_list",
    "date",
    "display_as",
    "famnick",
    "first_name",
    "group_as",
    "nick",
    "note_list",
    "private",
    "sort_as",
    "suffix",
    "surname_list",
    "title",
    "type",
}


def test_accepts_exactly_the_gramps_name_keys():
    """The model's keys match the Gramps Name schema one to one."""
    assert {f.alias or name for name, f in PersonName.model_fields.items()} == (
        GRAMPS_NAME_KEYS
    )


def test_bare_surname_in_primary_name_is_rejected_with_surname_list_hint():
    """The production payload fails and names the shape to use instead."""
    with pytest.raises(ValidationError) as exc_info:
        PersonData(primary_name={"first_name": "", "surname": "Sparks"}, gender=2)

    message = describe_validation_error(exc_info.value, PersonData)
    assert "primary_name" in message
    assert "'surname'" in message
    assert 'surname_list: [{"surname": "Sparks"}]' in message


def test_bare_surname_in_alternate_names_is_rejected():
    """Each alternate name gets the same check as the primary name."""
    with pytest.raises(ValidationError) as exc_info:
        PersonData(handle="p1", alternate_names=[{"surname": "Garcia"}])

    message = describe_validation_error(exc_info.value, PersonData)
    assert "alternate_names.0" in message
    assert 'surname_list: [{"surname": "Garcia"}]' in message


def test_other_unknown_key_suggests_the_close_name_key():
    """A typo of a real Name key points at that key."""
    with pytest.raises(ValidationError) as exc_info:
        PersonData(handle="p1", primary_name={"firstname": "Ada"})

    assert "'firstname' (did you mean 'first_name'?)" in str(exc_info.value)


def test_full_get_shaped_name_round_trips_unchanged():
    """A name copied from a GET, _class included, is sent back as it came."""
    name = {
        "_class": "Name",
        "first_name": "Ada",
        "surname_list": [
            {
                "_class": "Surname",
                "surname": "Lovelace",
                "primary": True,
                "origintype": {"_class": "NameOriginType", "string": "Inherited"},
            }
        ],
        "type": {"_class": "NameType", "string": "Birth Name"},
        "suffix": "",
        "display_as": 0,
        "citation_list": ["c1"],
        "private": False,
    }

    payload = PersonData(handle="p1", primary_name=name).to_api_payload()

    assert payload["primary_name"] == name


def test_partial_name_sends_only_the_supplied_keys():
    """Unset Name keys stay out of the body, as with the old plain dict."""
    payload = PersonData(
        handle="p1",
        alternate_names=[{"first_name": "Maria", "type": "Married Name"}],
    ).to_api_payload()

    assert payload["alternate_names"] == [
        {"first_name": "Maria", "type": "Married Name"}
    ]
