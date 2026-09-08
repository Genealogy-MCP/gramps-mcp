# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Composite-identity dedup for reference-object list merges.

When merging *_list fields on a PUT (list_mode="merge"), reference-object
entries (dicts carrying a "ref" handle plus qualifiers) must be deduped on
their full identity, not the "ref" alone -- otherwise genuinely-distinct
same-ref entries (media differing by rect, event refs differing by role) are
silently dropped.

child_ref_list is the exception and gets merge_child_refs: a Gramps family
holds at most one child_ref per child, so a second entry for the same child is
never correct. Entries merge by "ref", unioning their nested citation_list and
note_list, which is what lets a citation attach to an existing parent-child
edge (#60, #63).
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


def merge_child_refs(existing_items: list, new_items: list) -> list:
    """Merge child_ref entries by child handle, unioning their nested lists.

    A family holds one child_ref per child, so an incoming entry for a child
    already present updates that entry in place instead of appending a second
    one: nested citation_list/note_list are unioned and any explicitly supplied
    scalar (frel, mrel, private) overrides the stored value. Entries for
    children not yet in the family are appended.

    Args:
        existing_items (list): child_ref_list as returned by the merge GET.
        new_items (list): child_ref entries from the user's PUT payload.

    Returns:
        list: The merged child_ref_list.
    """
    merged = [dict(item) if isinstance(item, dict) else item for item in existing_items]
    index_by_ref = {
        item["ref"]: position
        for position, item in enumerate(merged)
        if isinstance(item, dict) and item.get("ref")
    }

    for new_item in new_items:
        if not isinstance(new_item, dict) or not new_item.get("ref"):
            continue
        position = index_by_ref.get(new_item["ref"])
        if position is None:
            index_by_ref[new_item["ref"]] = len(merged)
            merged.append(dict(new_item))
            continue

        target = merged[position]
        for key, value in new_item.items():
            # Reason: nested handle lists are additive evidence (a new
            # citation must not wipe the ones already on the edge), while a
            # supplied frel/mrel/private is a deliberate correction.
            if isinstance(value, list) and isinstance(target.get(key), list):
                target[key] = _merge_string_lists(target[key], value)
            else:
                target[key] = value

    return merged


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


def _merge_list_field(key: str, existing_items: list, new_items: list) -> list:
    """Merge one list field according to what its entries are.

    Args:
        key (str): The field name, which selects the child_ref_list policy.
        existing_items (list): Entries already stored.
        new_items (list): Entries from the PUT payload.

    Returns:
        list: The merged entries.
    """
    # Reason: a family holds one child_ref per child, so same-ref entries merge
    # in place instead of appending a duplicate edge -- that is what lets a
    # citation attach to an existing parent-child relationship (#60, #63).
    if key == "child_ref_list":
        return merge_child_refs(existing_items, new_items)
    if not existing_items or not new_items:
        return existing_items + new_items
    if isinstance(existing_items[0], dict) and isinstance(new_items[0], dict):
        return merge_ref_items(existing_items, new_items)
    if isinstance(existing_items[0], str) and isinstance(new_items[0], str):
        return _merge_string_lists(existing_items, new_items)
    return existing_items + new_items
