# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Ariel Castagnini
"""MR version collision check — fails when VERSION matches an existing tag.

Reads version from pyproject.toml, package.json, or VERSION file (in priority
order), validates it as semver, then checks the GitLab API for a matching tag.

Exit codes:
  0 — version is unreleased (safe to merge) or no version file found
  1 — tag collision detected, malformed version, or API error
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SEMVER_RE = re.compile(r"\d+\.\d+\.\d+(-[\w.]+)?(\+[\w.]+)?")


def read_version(root: str = ".") -> str | None:
    """Read version from pyproject.toml, package.json, or VERSION (priority order).

    Returns:
        Version string or None if no version file found.
    """
    base = Path(root)

    pyproject = base / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
        if m:
            return m.group(1)

    package_json = base / "package.json"
    if package_json.exists():
        return json.loads(package_json.read_text()).get("version")

    version_file = base / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    return None


def validate_version(version: str) -> str | None:
    """Validate version string. Returns error message or None if valid."""
    if "\n" in version or len(version) > 64:
        return "Version string is malformed (contains newlines or exceeds 64 chars)."
    if not SEMVER_RE.fullmatch(version):
        return f"Version '{version}' is not valid semver."
    return None


def check_tag_exists(version: str, api_url: str, project_id: str, job_token: str) -> bool:
    """Check if tag v{version} exists via GitLab API.

    Returns:
        True if tag exists, False if not (404).

    Raises:
        RuntimeError: On unexpected HTTP status.
    """
    safe_version = urllib.parse.quote(f"v{version}", safe="")
    url = f"{api_url}/projects/{project_id}/repository/tags/{safe_version}"
    req = urllib.request.Request(url, headers={"JOB-TOKEN": job_token})
    try:
        urllib.request.urlopen(req)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise RuntimeError(f"GitLab API returned {e.code}") from e


def main() -> int:
    """CLI entry point."""
    version = read_version()
    if not version:
        print("No version file found. Skipping version check.")
        return 0

    error = validate_version(version)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    api_url = os.environ["CI_API_V4_URL"]
    project_id = os.environ["CI_PROJECT_ID"]
    job_token = os.environ["CI_JOB_TOKEN"]

    try:
        if check_tag_exists(version, api_url, project_id, job_token):
            print(
                f"ERROR: Tag v{version} already exists. "
                "Bump the version in VERSION/pyproject.toml/package.json before merging.",
                file=sys.stderr,
            )
            return 1
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Version {version} is unreleased. OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
