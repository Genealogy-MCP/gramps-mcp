#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini
"""Check that Python source files contain the required AGPL-3.0 SPDX header."""

from __future__ import annotations

import sys
from pathlib import Path

SPDX_LINE = "# SPDX-License-Identifier: AGPL-3.0-only"
COPYRIGHT_LINE = "# Copyright (C)"
MAX_LINES = 20


def check_header(path: Path) -> bool:
    """Check for SPDX + copyright lines in the first MAX_LINES."""
    try:
        lines = path.read_text().splitlines()[:MAX_LINES]
    except (OSError, UnicodeDecodeError):
        return False

    has_spdx = any(SPDX_LINE in line for line in lines)
    has_copyright = any(COPYRIGHT_LINE in line for line in lines)
    return has_spdx and has_copyright


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} FILE [FILE ...]", file=sys.stderr)
        return 2

    failures: list[str] = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not check_header(path):
            failures.append(str(path))

    if failures:
        print("Missing AGPL-3.0 SPDX copyright header:")
        for f in failures:
            print(f"  {f}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
