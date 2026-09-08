# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Composite-identity dedup for reference-object list merges.

When merging *_list fields on a PUT (list_mode="merge"), reference-object
entries (dicts carrying a "ref" handle plus qualifiers) must be deduped on
their full identity, not the "ref" alone -- otherwise genuinely-distinct
same-ref entries (media differing by rect, child refs differing by
frel/mrel, event refs differing by role) are silently dropped.
"""

import json
from typing import Any


def _normalize_ref_item(item: dict) -> dict:
    """Reduce a reference-object to a canonical form for dedup keying.

    Recursively collapses typed enums ({"_class": ..., "string": S}) to the bare
    string S and drops keys whose value is a falsy default (None, [], {}, "",
    False). Meaningful integer 0 is preserved.

    Args:
        item (dict): A reference-object list element (e.g. a media or child ref).

    Returns:
        dict: A canonical copy used only for computing a dedup key.
    """
    normalized: dict = {}
    for key, value in item.items():
        # Reason: within one field's list every item shares its Gramps class
        # (all PlaceName, all Url), so _class carries no identity -- but only
        # the enriched GET form has it, so keeping it breaks dedup (#82).
        if key == "_class":
            continue
        canonical = _normalize_value(value)
        if canonical is None or canonical == [] or canonical == {}:
            continue
        if canonical == "" or canonical is False:
            continue
        normalized[key] = canonical
    return normalized


def _normalize_value(value: Any) -> Any:
    """Recursively canonicalize a value for dedup keying.

    Collapses typed enums to their bare string and recurses into dicts/lists.

    Args:
        value (Any): Any JSON-serializable value from a reference-object.

    Returns:
        Any: The canonicalized value.
    """
    if isinstance(value, dict):
        if set(value.keys()) == {"_class", "string"}:
            return value["string"]
        # Reason: GET expands an unset date into a full Date object of
        # defaults while the PUT payload omits it; both must key equal.
        # sortval is 0 only for empty dates (any real date computes a
        # nonzero serial), text covers text-only dates (#82).
        if "dateval" in value and not value.get("sortval") and not value.get("text"):
            return None
        return _normalize_ref_item(value)
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    return value


def merge_ref_items(existing_items: list, new_items: list) -> list:
    """Append new reference-objects to existing ones, deduped on composite identity.

    Each entry's dedup key is its full normalized dict serialized with sorted
    keys, so entries sharing a "ref" but differing in qualifiers both survive,
    while a re-PUT of an identical (logically equal) entry stays a single entry.

    Args:
        existing_items (list): Reference-objects already stored on the entity
            (enriched form from the merge GET).
        new_items (list): Reference-objects from the user's PUT payload
            (minimal form).

    Returns:
        list: existing_items followed by the new entries not already present.
    """
    # Reason: the merge GET returns the STORED entity in enriched form (private
    # false, empty sub-lists, typed-enum dicts) while the user's PUT payload is
    # minimal. Keying on the raw bytes would treat the same logical entry as
    # distinct and append a duplicate on every re-PUT. Normalizing both sides
    # first keeps merge idempotent.
    seen_keys = {
        json.dumps(_normalize_ref_item(item), sort_keys=True)
        for item in existing_items
        if isinstance(item, dict)
    }
    additions = [
        item
        for item in new_items
        if isinstance(item, dict)
        and json.dumps(_normalize_ref_item(item), sort_keys=True) not in seen_keys
    ]
    return existing_items + additions
