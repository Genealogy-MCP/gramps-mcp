# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""
Date data handler for Gramps MCP operations.

Provides clean, consistent date formatting from Gramps date objects.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _format_dateval_part(day: int, month: int, year: int) -> str | None:
    """
    Format a single [day, month, year] endpoint of a Gramps dateval.

    Args:
        day (int): Day of month, or 0 if unknown.
        month (int): Month number, or 0 if unknown.
        year (int): Year; values <= 0 are treated as missing.

    Returns:
        str | None: Human-readable date at the precision available, or None if
            the year is missing/invalid.
    """
    if year <= 0:
        return None

    try:
        if day > 0 and month > 0:
            return datetime(year, month, day).strftime("%d %B %Y")
        if month > 0:
            return datetime(year, month, 1).strftime("%B %Y")
        return str(year)
    except (ValueError, TypeError):
        return str(year) if year > 0 else None


def format_date(date_obj: dict) -> str:
    """
    Format Gramps date object into human-readable string with fallback.

    Args:
        date_obj (dict): Gramps date object with dateval array

    Returns:
        str: Formatted date string or "date unknown" if invalid
    """
    if not date_obj:
        return "date unknown"

    # Try formatted string first
    formatted_date = date_obj.get("string", "")
    if formatted_date:
        return formatted_date

    # Try to extract from dateval
    dateval = date_obj.get("dateval")
    if not dateval or len(dateval) < 3:
        return "date unknown"

    # dateval format is [day, month, year, dual]
    base_date = _format_dateval_part(dateval[0], dateval[1], dateval[2])
    if base_date is None:
        return "date unknown"

    quality = date_obj.get("quality", 0)
    modifier = date_obj.get("modifier", 0)

    modifier_prefixes = {
        0: "",  # regular
        1: "before ",
        2: "after ",
        3: "about ",
        4: "between ",  # range
        5: "from ",  # span
        6: "",  # textonly
        7: "from ",
        8: "to ",
    }

    quality_suffixes = {
        0: "",  # regular
        1: " (estimated)",
        2: " (calculated)",
    }

    suffix = quality_suffixes.get(quality, "")

    # Range (4) and span (5) carry a second endpoint in dateval[4:7].
    if modifier in (4, 5) and len(dateval) >= 7:
        end_date = _format_dateval_part(dateval[4], dateval[5], dateval[6])
        if end_date is not None:
            prefix = "between " if modifier == 4 else "from "
            joiner = "and" if modifier == 4 else "to"
            return f"{prefix}{base_date} {joiner} {end_date}{suffix}"

    prefix = modifier_prefixes.get(modifier, "")
    return f"{prefix}{base_date}{suffix}"
