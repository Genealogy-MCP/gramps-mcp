# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Rewrite GQL typed-enum name filters to the working ``type.value`` form.

The Gramps GQL engine evaluates filters against Python objects, and
``GrampsType`` has no ``.string`` attribute, so ``type.string = "Birth"``
silently matches nothing (HTTP 200, empty set -- issue #84, same failure
class as the ``private = True`` reject in ``_gql_hints``). ``type.value``
integer comparison is the only working path, so this module translates the
documented name syntax into it before the query reaches the API.

Name-to-int maps come from ``GET /api/types/default/{datatype}/map`` and are
cached for the server session. Delete this module once upstream Gramps Web
fixes GQL typed-enum matching (the integration regression probe flags that).
"""

import logging
import re
from typing import Dict, Mapping

from ..models.api_calls import ApiCalls

logger = logging.getLogger(__name__)

# Entity search key -> (GQL field name, types-endpoint datatype).
ENTITY_TYPE_FIELDS: Dict[str, tuple[str, str]] = {
    "events": ("type", "event_types"),
    "families": ("type", "family_relation_types"),
    "places": ("place_type", "place_types"),
    "repositories": ("type", "repository_types"),
}

# Session cache: datatype -> {type name: int value}.
_NAME_TO_VALUE_CACHE: Dict[str, Dict[str, int]] = {}


def _field_pattern(field: str) -> re.Pattern:
    # Matches `<field>.string <op> <value>` and the bare `<field> <op> <value>`
    # spelling, but not `<field>.value` (the dot after the field fails the
    # `\s*` before the operator). The lookbehind keeps `type` from firing
    # inside `place_type`. Only `=`/`!=` translate; `~` on a name has no
    # integer equivalent and passes through.
    return re.compile(
        rf"(?<![\w.]){re.escape(field)}(?:\.string)?"
        rf"\s*(!?=)\s*"
        rf"(\"[^\"]*\"|'[^']*'|\S+)"
    )


def rewrite_type_filters(
    gql: str, entity_type: str, name_to_value: Mapping[str, int]
) -> str:
    """Translate typed-enum name comparisons into ``<field>.value`` form.

    Args:
        gql (str): The caller's GQL query.
        entity_type (str): Search entity key (``"events"``, ``"places"``, ...).
        name_to_value (Mapping[str, int]): Default type name to integer map.

    Returns:
        str: The query with known name comparisons rewritten; anything the
        map does not know (custom names, other fields) is left untouched.
    """
    entry = ENTITY_TYPE_FIELDS.get(entity_type)
    if not entry:
        return gql
    field, _ = entry

    def _translate(match: re.Match) -> str:
        op = match.group(1)
        raw = match.group(2)
        name = raw[1:-1] if raw[0] in "\"'" else raw
        value = name_to_value.get(name)
        if value is None:
            return match.group(0)
        return f"{field}.value {op} {value}"

    return _field_pattern(field).sub(_translate, gql)


async def get_name_to_value_map(client, entity_type: str) -> Dict[str, int]:
    """Fetch and cache the default type name-to-int map for an entity.

    Args:
        client: Gramps API client instance.
        entity_type (str): Search entity key from ``ENTITY_TYPE_FIELDS``.

    Returns:
        Dict[str, int]: Type name to integer value (empty for entities
        without a typed enum).
    """
    entry = ENTITY_TYPE_FIELDS.get(entity_type)
    if not entry:
        return {}
    _, datatype = entry
    if datatype not in _NAME_TO_VALUE_CACHE:
        raw = await client.make_api_call(
            ApiCalls.GET_TYPES_DEFAULT_MAP, datatype=datatype
        )
        _NAME_TO_VALUE_CACHE[datatype] = {
            name: int(value) for value, name in raw.items()
        }
    return _NAME_TO_VALUE_CACHE[datatype]


async def maybe_rewrite_gql(client, entity_type: str, gql: str) -> str:
    """Rewrite a query's typed-enum name filters if the entity has any.

    Fetches the name map only when the query actually mentions the type
    field, so unrelated searches never pay the extra API call.

    Args:
        client: Gramps API client instance.
        entity_type (str): Search entity key (``"events"``, ``"places"``, ...).
        gql (str): The caller's GQL query.

    Returns:
        str: The rewritten query, or the original when nothing applies.
    """
    entry = ENTITY_TYPE_FIELDS.get(entity_type)
    if not gql or not entry:
        return gql
    field, _ = entry
    if not _field_pattern(field).search(gql):
        return gql
    try:
        name_to_value = await get_name_to_value_map(client, entity_type)
    except Exception as exc:
        # Reason: the rewrite is best-effort sugar; a failed type-map fetch
        # must not mask the real search (whose own errors carry GQL hints).
        logger.warning(
            "Type-map fetch failed for %s; sending GQL unrewritten: %s",
            entity_type,
            exc,
        )
        return gql
    return rewrite_type_filters(gql, entity_type, name_to_value)
