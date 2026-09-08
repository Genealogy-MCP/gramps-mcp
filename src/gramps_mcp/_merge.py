# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Composite-identity dedup for reference-object list merges.

When merging *_list fields on a PUT (list_mode="merge"), reference-object
entries (dicts carrying a "ref" handle plus qualifiers) must be deduped on
their full identity, not the "ref" alone -- otherwise genuinely-distinct
same-ref entries (media differing by rect, child refs differing by
frel/mrel, event refs differing by role) are silently dropped.

placeref_list is the exception and gets merge_place_refs: a place sits inside
exactly one parent at a time, so an undated enclosure replaces the stored
undated one rather than appending a second parent (#67).
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
        # Emptiness keys on dateval (all zeros) plus no text, and sortval
        # is dropped because the server computes it and PUT payloads
        # legitimately omit it -- keying on it would append a duplicate
        # on every re-PUT of a dated entry (#82).
        if "dateval" in value:
            if not any(value.get("dateval") or []) and not value.get("text"):
                return None
            return _normalize_ref_item(
                {k: v for k, v in value.items() if k != "sortval"}
            )
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


def _has_date(item: Any) -> bool:
    """Report whether a place reference carries a real date qualifier.

    A dated entry describes a time-limited historic enclosure; an undated one
    is the place's current parent.

    Args:
        item (Any): One placeref_list entry, as stored or as supplied.

    Returns:
        bool: True when the entry's "date" names an actual time.
    """
    if not isinstance(item, dict):
        return False
    # Reason: Gramps Web returns an *empty Date object* rather than null for an
    # undated placeref -- dateval [0, 0, 0, False], year 0, text "" -- so a
    # truthiness check on "date" marks every stored entry as dated (#67).
    date = item.get("date")
    if not isinstance(date, dict):
        return bool(date)
    if date.get("text"):
        return True
    dateval = date.get("dateval") or []
    return any(bool(part) for part in dateval)


def merge_place_refs(existing_items: list, new_items: list) -> list:
    """Merge placeref_list entries, treating the undated enclosure as singular.

    A place sits inside exactly one parent at a time, so an incoming undated
    entry replaces the stored undated one instead of appending a second parent
    -- otherwise re-parenting a place through enclosed_by would leave it with
    two parents and no error (#67). Date-qualified entries record historic
    enclosures, so they accumulate and dedup on their full identity.

    Args:
        existing_items (list): placeref_list as returned by the merge GET.
        new_items (list): placeref_list entries from the caller's PUT payload.

    Returns:
        list: The merged placeref_list.
    """
    incoming_undated = [item for item in new_items if not _has_date(item)]
    if not incoming_undated:
        return merge_ref_items(existing_items, new_items)

    # Reason: only the last undated entry supplied can be "the" current parent,
    # so an accidental list of several collapses to the caller's final word
    # rather than silently stacking parents.
    kept = [item for item in existing_items if _has_date(item)]
    dated_new = [item for item in new_items if _has_date(item)]
    return merge_ref_items(kept, dated_new) + [incoming_undated[-1]]


def _merge_string_lists(existing_items: list, new_items: list) -> list:
    """Append the new string handles not already present, preserving order.

    Args:
        existing_items (list): Handles already stored.
        new_items (list): Handles from the PUT payload.

    Returns:
        list: existing_items followed by the genuinely new handles.
    """
    seen = set(existing_items)
    return existing_items + [item for item in new_items if item not in seen]


def _merge_list_field(key: str, existing_items: list, new_items: list) -> list:
    """Merge one list field according to what its entries are.

    Args:
        key (str): The field name, which selects the placeref_list policy.
        existing_items (list): Entries already stored.
        new_items (list): Entries from the PUT payload.

    Returns:
        list: The merged entries.
    """
    # Reason: a place has one current parent, so re-parenting must replace the
    # stored undated enclosure rather than stack a second one (#67).
    if key == "placeref_list":
        return merge_place_refs(existing_items, new_items)
    if not existing_items or not new_items:
        return existing_items + new_items
    # Reason: dict entries dedup on composite identity, not "ref" alone, so
    # distinct same-ref entries (media rect, child frel/mrel) both survive and
    # re-PUTs of value collections stay idempotent (#82).
    if isinstance(existing_items[0], dict) and isinstance(new_items[0], dict):
        return merge_ref_items(existing_items, new_items)
    if isinstance(existing_items[0], str) and isinstance(new_items[0], str):
        return _merge_string_lists(existing_items, new_items)
    return existing_items + new_items


def merge_object(existing: dict, changes: dict, list_mode: str) -> dict:
    """Overlay a PUT payload onto the stored object, merging list fields.

    Args:
        existing (dict): The entity as currently stored, from the merge GET.
        changes (dict): The caller's PUT payload.
        list_mode (str): "merge" to append to stored lists, "replace" to
            overwrite them wholesale.

    Returns:
        dict: The stored object with the caller's changes applied.
    """
    merged = existing.copy()
    for key, value in changes.items():
        stored = existing.get(key)
        # Reason: a field is a mergeable collection when BOTH sides hold a
        # list -- keying on the "_list" name convention silently replaced
        # alt_names, urls, alternate_names, and alt_loc (#82).
        if list_mode != "merge" or not isinstance(value, list):
            merged[key] = value
        elif not isinstance(stored, list):
            merged[key] = value
        else:
            merged[key] = _merge_list_field(key, stored, value)
    return merged
