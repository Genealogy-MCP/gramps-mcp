# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 Federico Castagnini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
GQL smart hints for common search mistakes.

When a GQL query returns zero results, these hints detect likely property-path
errors and suggest the correct path. Only fires on known mistake patterns --
returns empty string when the query looks correct.
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
}


def gql_hint(entity_type: str, gql: str) -> str:
    """
    Return a corrective hint if the GQL query contains a known mistake.

    Args:
        entity_type: The plural entity type (e.g. "people", "places").
        gql: The raw GQL query string.

    Returns:
        A hint message if a known mistake is detected, empty string otherwise.
    """
    if not gql:
        return ""

    patterns = _GQL_HINTS.get(entity_type, [])
    for regex, hint in patterns:
        if regex.search(gql):
            return hint

    return ""
