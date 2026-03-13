#!/usr/bin/env python3
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
Pre-commit hook to verify AGPL-3.0 copyright headers on source files.

This project is a fork of gramps-mcp by cabout.me, licensed under AGPL-3.0.
Section 5 of the AGPL requires that derivative works retain the original
copyright notice and mark modified files with the new author and date.
This check ensures every source file carries the required header so the
project stays in compliance.

Checks that every Python file in src/ and scripts/ contains the project
identifier line and the AGPL license reference within the first 20 lines.
Test files are excluded (matching original repo convention).
"""

import sys
from pathlib import Path

PROJECT_LINE = "# gramps-mcp - AI-Powered Genealogy Research & Management"
LICENSE_LINE = "# GNU Affero General Public License"

# Reason: 20 lines covers shebang + full header block with room to spare
MAX_HEADER_LINES = 20


def check_header(file_path: Path) -> bool:
    """
    Check that a file contains the required AGPL copyright header.

    Args:
        file_path: Path to the Python file to check.

    Returns:
        bool: True if the header is present, False otherwise.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            head = [f.readline() for _ in range(MAX_HEADER_LINES)]
    except Exception as e:
        print(f"ERROR: Could not read {file_path}: {e}")
        return False

    text = "".join(head)
    has_project = PROJECT_LINE in text
    has_license = LICENSE_LINE in text

    if not has_project or not has_license:
        missing = []
        if not has_project:
            missing.append("project identifier")
        if not has_license:
            missing.append("AGPL license reference")
        print(f"ERROR: {file_path} missing copyright header ({', '.join(missing)})")
        return False

    return True


def main() -> int:
    """
    Check all provided files for copyright headers.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    if len(sys.argv) < 2:
        print("Usage: check_copyright_header.py <file1> [file2] ...")
        return 1

    all_passed = True

    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)

        if not file_path.suffix == ".py":
            continue

        if not check_header(file_path):
            all_passed = False

    if not all_passed:
        print()
        print("Add the AGPL-3.0 copyright header to the files listed above.")
        print("See existing src/ files for the expected format.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
