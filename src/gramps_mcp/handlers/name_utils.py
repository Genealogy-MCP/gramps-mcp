# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Shared name formatting utilities for Gramps person data.

Provides join_surnames() for building full surname strings from
Gramps surname_list arrays, supporting multi-surname naming conventions
(e.g. Hispanic, Portuguese, double-barrelled names).
"""

from typing import Any, List, Optional


def join_surnames(surname_list: Optional[List[Any]]) -> str:
    """Join all surnames from a Gramps surname_list into a single string.

    Gramps stores surnames as a list of dicts, each with a "surname" key.
    Many naming conventions use multiple surnames (e.g. Hispanic paternal +
    maternal). This function joins all of them with spaces, instead of
    taking only the first entry.

    Args:
        surname_list: List of surname dicts from person primary_name data.
            Each entry should have a "surname" key. None and empty lists
            are handled gracefully.

    Returns:
        Space-joined string of all non-empty surnames, or empty string
        if no valid surnames are found.
    """
    if not surname_list:
        return ""

    parts = []
    for entry in surname_list:
        if isinstance(entry, dict):
            value = entry.get("surname", "").strip()
            if value:
                parts.append(value)

    return " ".join(parts)
