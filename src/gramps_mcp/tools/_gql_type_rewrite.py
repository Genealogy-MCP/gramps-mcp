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
from dataclasses import dataclass
from typing import Dict, FrozenSet, Mapping, Optional, Tuple

from ..models.api_calls import ApiCalls
from ._errors import McpToolError

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

# Session cache: datatype -> custom type names from GET types/custom/{datatype}.
_CUSTOM_NAMES_CACHE: Dict[str, FrozenSet[str]] = {}


@dataclass(frozen=True)
class PostFilter:
    """Client-side match a rewritten custom-name clause still requires.

    The server can only pre-filter to ``<field>.value = <Custom int>``; the
    exact custom name is matched on the returned rows.
    """

    field: str
    name: str


@dataclass(frozen=True)
class TypeRewrite:
    """Result of a typed-enum rewrite: the query plus any post filters."""

    gql: str
    post_filters: Tuple[PostFilter, ...] = ()


def matches_post_filters(obj: Mapping, post_filters: Tuple[PostFilter, ...]) -> bool:
    """Check a returned object against the custom-name post filters.

    Args:
        obj (Mapping): The API object (search-result ``object`` unwrapped).
        post_filters (Tuple[PostFilter, ...]): Filters from the rewrite.

    Returns:
        bool: True when every filter's field carries the expected name.
    """
    for pf in post_filters:
        value = obj.get(pf.field)
        # The API serializes types as a plain string; older shapes use the
        # {"_class": ..., "string": ...} object form.
        if isinstance(value, dict):
            value = value.get("string")
        if value != pf.name:
            return False
    return True


def apply_post_filters(results, post_filters: Tuple[PostFilter, ...]) -> list:
    """Drop fetched rows whose type string fails the custom-name match.

    The server pre-filter only narrows to the ``Custom`` integer; this is
    the exact-name half of the #85 rewrite. Search-result wrappers are
    unwrapped via their ``object`` key.

    Args:
        results: Raw result items from the search API call.
        post_filters (Tuple[PostFilter, ...]): Filters from the rewrite.

    Returns:
        list: The surviving items (all of them when there are no filters).
    """
    if not post_filters:
        return results
    return [
        item
        for item in results
        if isinstance(item, dict)
        and matches_post_filters(item.get("object", item), post_filters)
    ]


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
    gql: str,
    entity_type: str,
    name_to_value: Mapping[str, int],
    custom_names: Optional[FrozenSet[str]] = None,
) -> TypeRewrite:
    """Translate typed-enum name comparisons into ``<field>.value`` form.

    Default names rewrite to their integer. Custom names (issue #85) rewrite
    to the ``Custom`` integer pre-filter plus a client-side post filter on
    the returned type string. A name that is neither default nor custom
    raises an actionable error instead of silently matching nothing.

    Args:
        gql (str): The caller's GQL query.
        entity_type (str): Search entity key (``"events"``, ``"places"``, ...).
        name_to_value (Mapping[str, int]): Default type name to integer map.
        custom_names (Optional[FrozenSet[str]]): Custom type names for the
            entity, or None when the custom list could not be fetched (falls
            back to passing unknown names through untouched).

    Returns:
        TypeRewrite: The rewritten query and any client-side post filters.

    Raises:
        McpToolError: Unknown type name, ``!=`` on a custom name, or a
            custom name inside an ``or`` query (the post filter is only
            correct under ``and`` semantics).
    """
    entry = ENTITY_TYPE_FIELDS.get(entity_type)
    if not entry:
        return TypeRewrite(gql)
    field, _ = entry
    post_filters: list[PostFilter] = []

    def _translate(match: re.Match) -> str:
        op = match.group(1)
        raw = match.group(2)
        name = raw[1:-1] if raw[0] in "\"'" else raw
        value = name_to_value.get(name)
        if value is not None:
            return f"{field}.value {op} {value}"
        if custom_names is None or name not in custom_names:
            if custom_names is None:
                # Custom list unavailable: keep the pre-#85 passthrough.
                return match.group(0)
            known = ", ".join(
                sorted(n for n in name_to_value if n != "Custom") + sorted(custom_names)
            )
            raise McpToolError(
                f"Unknown {entity_type} type name '{name}'. Known type names: {known}."
            )
        custom_value = name_to_value.get("Custom")
        if custom_value is None:
            return match.group(0)
        if op != "=":
            raise McpToolError(
                f"'{op}' is not supported on the custom type name '{name}'; "
                f"only '=' works. Use {field}.value comparisons instead."
            )
        if re.search(r"\bor\b", gql, re.IGNORECASE):
            raise McpToolError(
                f"The custom type name '{name}' cannot be combined with 'or': "
                "custom names match client-side, which is only correct for "
                "'and' queries. Split the query or use "
                f"{field}.value comparisons."
            )
        post_filters.append(PostFilter(field=field, name=name))
        return f"{field}.value {op} {custom_value}"

    rewritten = _field_pattern(field).sub(_translate, gql)
    return TypeRewrite(rewritten, tuple(post_filters))


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


async def get_custom_names(client, entity_type: str) -> Optional[FrozenSet[str]]:
    """Fetch and cache the custom type names for an entity.

    Args:
        client: Gramps API client instance.
        entity_type (str): Search entity key from ``ENTITY_TYPE_FIELDS``.

    Returns:
        Optional[FrozenSet[str]]: Custom names, or None when the fetch failed
        (the rewrite then falls back to passing unknown names through).
    """
    entry = ENTITY_TYPE_FIELDS.get(entity_type)
    if not entry:
        return frozenset()
    _, datatype = entry
    if datatype not in _CUSTOM_NAMES_CACHE:
        try:
            raw = await client.make_api_call(
                ApiCalls.GET_TYPES_CUSTOM_DATATYPE, datatype=datatype
            )
        except Exception as exc:
            # Reason: a failed custom-list fetch must not turn every unknown
            # name into a hard error; degrade to the pre-#85 passthrough.
            logger.warning("Custom type-name fetch failed for %s: %s", entity_type, exc)
            return None
        _CUSTOM_NAMES_CACHE[datatype] = frozenset(str(n) for n in raw)
    return _CUSTOM_NAMES_CACHE[datatype]


async def maybe_rewrite_gql(client, entity_type: str, gql: str) -> TypeRewrite:
    """Rewrite a query's typed-enum name filters if the entity has any.

    Fetches the name maps only when the query actually mentions the type
    field, so unrelated searches never pay the extra API calls.

    Args:
        client: Gramps API client instance.
        entity_type (str): Search entity key (``"events"``, ``"places"``, ...).
        gql (str): The caller's GQL query.

    Returns:
        TypeRewrite: The rewritten query plus any custom-name post filters,
        or the original query when nothing applies.

    Raises:
        McpToolError: Unknown type name or an unsupported custom-name query
        shape (see :func:`rewrite_type_filters`).
    """
    entry = ENTITY_TYPE_FIELDS.get(entity_type)
    if not gql or not entry:
        return TypeRewrite(gql)
    field, _ = entry
    if not _field_pattern(field).search(gql):
        return TypeRewrite(gql)
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
        return TypeRewrite(gql)
    custom_names = await get_custom_names(client, entity_type)
    return rewrite_type_filters(gql, entity_type, name_to_value, custom_names)


async def rewrite_search_args(client, entity_type: str, arguments: Dict):
    """Apply the typed-enum rewrite to a search's ``gql`` argument.

    Convenience wrapper for the search tools: returns the (possibly
    replaced) arguments dict plus the post filters to run on the results.

    Args:
        client: Gramps API client instance.
        entity_type (str): Search entity key (``"events"``, ``"places"``, ...).
        arguments (Dict): The tool's raw arguments.

    Returns:
        tuple[Dict, Tuple[PostFilter, ...]]: Arguments with ``gql``
        rewritten when needed, and the custom-name post filters.
    """
    gql = arguments.get("gql")
    if not gql:
        return arguments, ()
    rewrite = await maybe_rewrite_gql(client, entity_type, gql)
    if rewrite.gql != gql:
        arguments = {**arguments, "gql": rewrite.gql}
    return arguments, rewrite.post_filters
