#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Refresh the pinned OpenAPI snapshot from the Docker test instance.

Fetches `/api/openapi.json` and `/api/metadata/`, refuses a server whose
gramps-webapi version differs from `schema_pin.SCHEMA_VERSION` (unless
told otherwise), writes `schema/openapi.json` plus its sidecar, regenerates
`src/gramps_mcp/resource_table.py`, and prints the table diff.

Usage:
    python scripts/schema_fetch.py [--base-url URL]
    python scripts/schema_fetch.py --allow-version-mismatch   # bumping the pin
    GRAMPS_SCHEMA_ALLOW_MISMATCH=1 python scripts/schema_fetch.py

Never writes to stdout except the diff; status goes to stderr.
"""

import argparse
import datetime as dt
import difflib
import json
import os
import re
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.gramps_mcp import codegen  # noqa: E402
from src.gramps_mcp.schema_pin import SCHEMA_VERSION  # noqa: E402

DEFAULT_BASE_URL = "http://localhost:5055"
DEFAULT_USERNAME = "owner"
DEFAULT_PASSWORD = "owner"
COMPOSE_FILE = REPO_ROOT / "docker-compose.test.yml"
IMAGE_RE = re.compile(r"^\s*image:\s*(ghcr\.io/gramps-project/grampsweb:\S+)", re.M)
TIMEOUT = 30.0


def docker_image() -> str:
    """The grampsweb image line of the compose file, for the sidecar."""
    match = IMAGE_RE.search(COMPOSE_FILE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"no grampsweb image line in {COMPOSE_FILE}")
    return match.group(1)


def fetch(base_url: str, username: str, password: str) -> tuple[bytes, dict]:
    """Return the raw OpenAPI bytes and the parsed metadata document.

    The OpenAPI document is public; `/api/metadata/` needs a JWT.
    """
    with httpx.Client(base_url=base_url, timeout=TIMEOUT) as client:
        spec = client.get("/api/openapi.json")
        spec.raise_for_status()
        token = client.post(
            "/api/token/", json={"username": username, "password": password}
        )
        token.raise_for_status()
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
        metadata = client.get("/api/metadata/", headers=headers)
        metadata.raise_for_status()
    return spec.content, metadata.json()


def table_diff(before: str, after: str) -> str:
    """Unified diff of the resource table around the refresh."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="resource_table.py (before)",
            tofile="resource_table.py (after)",
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Fetch, pin-check, write snapshot + sidecar, regenerate, diff."""
    parser = argparse.ArgumentParser(
        description="Refresh the pinned OpenAPI snapshot from the Docker test instance."
    )
    # Reason: the shell often carries GRAMPS_* credentials for the live tree;
    # the snapshot must come from the Docker test instance, so nothing here
    # reads them. Pass flags to target another server deliberately.
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--allow-version-mismatch",
        action="store_true",
        default=os.environ.get("GRAMPS_SCHEMA_ALLOW_MISMATCH") == "1",
        help="accept a server version other than SCHEMA_VERSION (bump the pin after)",
    )
    args = parser.parse_args(argv)

    spec_bytes, metadata = fetch(args.base_url, args.username, args.password)
    live_version = str(metadata["gramps_webapi"]["version"])
    if live_version != SCHEMA_VERSION and not args.allow_version_mismatch:
        sys.stderr.write(
            f"server runs gramps-webapi {live_version}, snapshot is pinned to "
            f"{SCHEMA_VERSION}. Rerun with --allow-version-mismatch and update "
            "src/gramps_mcp/schema_pin.py in the same change.\n"
        )
        return 2

    spec = json.loads(spec_bytes)
    pretty = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    pretty_bytes = pretty.encode("utf-8")
    sidecar = codegen.build_sidecar(
        spec_bytes=pretty_bytes,
        source_url=f"{args.base_url.rstrip('/')}/api/openapi.json",
        docker_image=docker_image(),
        metadata=metadata,
        openapi_version=str(spec.get("openapi", "")),
        fetched_on=dt.date.today().isoformat(),
    )

    before = (
        codegen.TABLE_PATH.read_text(encoding="utf-8")
        if codegen.TABLE_PATH.exists()
        else ""
    )
    codegen.SCHEMA_DIR.mkdir(exist_ok=True)
    codegen.SNAPSHOT_PATH.write_bytes(pretty_bytes)
    codegen.SIDECAR_PATH.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Reason: render from the bytes written, not the raw response, so the table
    # matches what `codegen --check` rebuilds from the sorted snapshot.
    after = codegen.generate(json.loads(pretty))
    codegen.TABLE_PATH.write_text(after, encoding="utf-8")

    sys.stderr.write(
        f"snapshot: gramps-webapi {live_version}, sha256 {sidecar['sha256'][:12]}...\n"
    )
    diff = table_diff(before, after)
    sys.stdout.write(diff if diff else "resource table unchanged\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
