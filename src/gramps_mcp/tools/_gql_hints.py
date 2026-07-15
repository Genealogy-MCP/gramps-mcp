# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
GQL smart hints for common search mistakes.

When a GQL query returns zero results or errors, these hints detect likely
property-path errors and suggest the correct path. Only fires on known
mistake patterns -- returns empty string when the query looks correct.
"""

import re
from typing import Dict, List, Tuple

# Patterns per entity type: (compiled_regex, hint_message)
# Regex uses negative lookbehind (?<!\.) so dotted paths like
# primary_name.first_name do NOT trigger a false positive.
_GQL_HINTS: Dict[str, List[Tuple[re.Pattern, str]]] = {
    "people": [
        (
            re.compile(r"(?<!\.)(?<!\w)\bname\b", re.IGNORECASE),
            (
                "Person names use 'primary_name.first_name' for first names "
                "and 'primary_name.surname_list[0].surname' for surnames. "
                "'name' is not a valid Person property in GQL."
            ),
        ),
        (
            re.compile(r"(?<!\.)(?<!\w)\bsurname\b", re.IGNORECASE),
            (
                "Use 'primary_name.surname_list[0].surname' to search "
                "by surname. 'surname' alone is not a valid Person property."
            ),
        ),
        (
            re.compile(r"(?<!\.)(?<!\w)\b(?:firstname|first_name)\b", re.IGNORECASE),
            (
                "Use 'primary_name.first_name' to search by first name. "
                "'first_name' alone is not a valid Person property."
            ),
        ),
    ],
    "places": [
        (
            re.compile(r"(?<!\.)(?<!\w)\bname\b(?!\.value)", re.IGNORECASE),
            (
                "Place names use 'name.value' (not bare 'name'). "
                'Example: name.value ~ "Boston"'
            ),
        ),
        (
            re.compile(r"(?<!\.)(?<!\w)\btype\b(?!\.string)", re.IGNORECASE),
            (
                "Place types use 'place_type.string' (not 'type'). "
                "Example: place_type.string = City"
            ),
        ),
    ],
    "events": [
        (
            re.compile(r"(?<!\.)(?<!\w)\btype\b(?!\.string)", re.IGNORECASE),
            (
                "Event types use 'type.string' (not bare 'type'). "
                "Example: type.string = Birth"
            ),
        ),
    ],
    "families": [
        (
            re.compile(r"(?<!\.)(?<!\w)\btype\b(?!\.string)", re.IGNORECASE),
            (
                "Family relationship types use 'type.string' (not bare 'type'). "
                "Example: type.string = Married"
            ),
        ),
    ],
    "repositories": [
        (
            re.compile(r"(?<!\.)(?<!\w)\btype\b(?!\.string)", re.IGNORECASE),
            (
                "Repository types use 'type.string' (not bare 'type'). "
                "Example: type.string = Archive"
            ),
        ),
    ],
    "notes": [
        (
            re.compile(r"(?<!\.)(?<!\w)\btext\b(?!\.string)", re.IGNORECASE),
            (
                "Note text uses 'text.string' (not bare 'text'). "
                'Example: text.string ~ "research"'
            ),
        ),
    ],
}

# Cross-entity patterns that apply to all entity types.
# Detects unquoted multi-word values after the ~ operator.
_GLOBAL_GQL_HINTS: List[Tuple[re.Pattern, str]] = [
    (
        re.compile(r'~\s+(?!")(\w+)\s+(?!and\b|or\b)(\w+)', re.IGNORECASE),
        (
            "Multi-word GQL values must be quoted. "
            'Example: name.value ~ "Capital Federal" (not name.value ~ Capital Federal)'
        ),
    ),
]


# Boolean-literal comparison on the `private` field. The Gramps GQL engine
# silently returns an empty set for these (verified against the Docker test
# instance): `private = True/False` and `private != True/False` never filter,
# so an LLM reading `[]` wrongly concludes "no private records exist". This is
# a hard-reject detector, distinct from gql_hint's post-hoc advice -- it fires
# BEFORE the API call. `private`-only by design: a general boolean detector
# would false-positive on fields that legitimately compare booleans.
# `private = 1` / `private = 0` / bare `private` are the syntaxes that work,
# so they are deliberately not matched.
_PRIVATE_BOOL_LITERAL = re.compile(r"\bprivate\s*!?=\s*(?:true|false)\b", re.IGNORECASE)

_PRIVATE_REJECT_MESSAGE = (
    "GQL cannot filter the `private` field with a boolean literal "
    "(`private = True`, `private = False`, `private != True`) -- the Gramps "
    "engine silently returns an empty set, which falsely reads as 'no private "
    "records exist'. Use the bare truthy check `private` (private records "
    "only) or the integer form `private = 1` / `private = 0` instead. "
    "Alternatively, list the records and filter client-side on the visible "
    "`private` field."
)


def gql_private_reject(gql: str) -> str:
    """
    Return a hard-reject error message if the GQL query filters `private`
    with a boolean literal, empty string otherwise.

    Unlike gql_hint (which appends advice to an already-empty result), this
    detector is meant to be consulted BEFORE the API call so the caller never
    sees a misleading empty result set (see issue #54).

    Args:
        gql: The raw GQL query string.

    Returns:
        The actionable error message when a boolean-literal `private`
        comparison is present, empty string when the query is safe to run.
    """
    if not gql:
        return ""

    if _PRIVATE_BOOL_LITERAL.search(gql):
        return _PRIVATE_REJECT_MESSAGE

    return ""


def gql_hint(entity_type: str, gql: str) -> str:
    """
    Return corrective hints if the GQL query contains known mistakes.

    Collects all matching hints (entity-specific and global) and joins
    them with newlines.

    Args:
        entity_type: The plural entity type (e.g. "people", "places").
        gql: The raw GQL query string.

    Returns:
        Joined hint messages if known mistakes are detected, empty string otherwise.
    """
    if not gql:
        return ""

    hints: List[str] = []

    for regex, hint in _GQL_HINTS.get(entity_type, []):
        if regex.search(gql):
            hints.append(hint)

    for regex, hint in _GLOBAL_GQL_HINTS:
        if regex.search(gql):
            hints.append(hint)

    return "\n".join(hints)
