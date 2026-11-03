#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Seed a local Gramps Web Docker instance with test data.

Waits for the service to be healthy, creates an owner user and an
Editor-role user, imports the vendored seed.gramps fixture, and rebuilds
the search index.

Usage:
    python scripts/seed_test_db.py [--base-url URL] [--timeout SECONDS]
    python scripts/seed_test_db.py --skip-if-seeded  # no-op when integrity probe passes
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests._test_env import (  # noqa: E402
    EDITOR_PASSWORD,
    EDITOR_USERNAME,
    resolve_base_url,
)

SEED_FILE = REPO_ROOT / "tests" / "fixtures" / "seed.gramps"
DEFAULT_USERNAME = "owner"
DEFAULT_PASSWORD = "owner"
DEFAULT_TIMEOUT = 120

# gramps-webapi role levels (gramps_webapi.auth.const).
ROLE_EDITOR = 3
ROLE_OWNER = 4

# Exact entity counts in tests/fixtures/seed.gramps, used as floors by
# verify_data. Re-derive after replacing the fixture by counting the
# "<person ", "<source " and "<citation " tags in the gunzipped XML.
FIXTURE_COUNTS = {
    "people": 2157,
    "sources": 4,
    "citations": 2854,
}


def wait_for_healthy(base_url: str, timeout: float) -> None:
    """
    Poll the root URL until the service responds with HTTP 200.

    Args:
        base_url: Gramps Web base URL (e.g. http://127.0.0.1:54321).
        timeout: Maximum seconds to wait.

    Raises:
        SystemExit: If the service does not become healthy within timeout.
    """
    deadline = time.monotonic() + timeout
    delay = 1.0
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            resp = httpx.get(f"{base_url}/", timeout=5)
            if resp.status_code == 200:
                print(f"Service healthy after {attempt} attempts")
                return
        except httpx.ConnectError:
            pass
        except httpx.ReadTimeout:
            pass
        time.sleep(min(delay, deadline - time.monotonic()))
        delay = min(delay * 1.5, 10.0)
    print(f"Service at {base_url} not healthy after {timeout}s", file=sys.stderr)
    sys.exit(1)


def create_user(compose_file: str, username: str, password: str, role: int) -> None:
    """
    Create a user with the given role via docker compose exec.

    The Gramps Web API does not expose a reliable user-creation endpoint,
    so we use the CLI inside the container.

    Args:
        compose_file: Path to docker-compose.test.yml.
        username: Username.
        password: Password.
        role: gramps-webapi role level (ROLE_EDITOR, ROLE_OWNER).
    """
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            compose_file,
            "exec",
            "-T",
            "grampsweb",
            "python3",
            "-m",
            "gramps_webapi",
            "user",
            "add",
            username,
            password,
            "--role",
            str(role),
            "--email",
            f"{username}@test.com",
        ],
        capture_output=True,
        text=True,
        # Reason: each call boots gramps_webapi, past 30s under parallel stacks (#124).
        timeout=DEFAULT_TIMEOUT,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "already exists" in stderr.lower() or "unique constraint" in stderr.lower():
            print(f"User '{username}' already exists (OK for reruns)")
            return
        print(f"Failed to create user: {stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Created user '{username}' (role {role})")


def authenticate(base_url: str, username: str, password: str) -> str:
    """
    Obtain a JWT access token.

    Args:
        base_url: Gramps Web base URL.
        username: Username.
        password: Password.

    Returns:
        The JWT access token string.

    Raises:
        SystemExit: On authentication failure.
    """
    resp = httpx.post(
        f"{base_url}/api/token/",
        json={"username": username, "password": password},
        timeout=10,
    )
    if resp.status_code != 200:
        print(
            f"Authentication failed ({resp.status_code}): {resp.text}", file=sys.stderr
        )
        sys.exit(1)
    token = resp.json()["access_token"]
    print("Authenticated successfully")
    return token


def is_already_seeded(base_url: str, token: str) -> bool:
    """
    Integrity-probe the test database for intact seed data.

    A bare "any person exists" check reads a partially damaged tree as
    seeded, so this probes two specific anchor records from the fixture:
    person I0001 and repository R0000. Both must resolve over a healthy
    (HTTP 200) API for the tree to count as seeded; anything else means
    the caller should reset and reseed.

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.

    Returns:
        True if both anchor records are present and the API is healthy.
    """
    headers = {"Authorization": f"Bearer {token}"}
    probes = [
        ("person I0001", f"{base_url}/api/people/?gramps_id=I0001"),
        ("repository R0000", f"{base_url}/api/repositories/?gramps_id=R0000"),
    ]
    try:
        for label, url in probes:
            resp = httpx.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"  Integrity probe: HTTP {resp.status_code} on {label}")
                return False
            if not resp.json():
                print(f"  Integrity probe: {label} missing")
                return False
        return True
    except httpx.TransportError:
        return False


def poll_task(
    base_url: str,
    token: str,
    task_id: str,
    timeout: float,
    compose_file: str = "",
) -> dict | None:
    """
    Poll a Celery task until it reaches a terminal state.

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.
        task_id: Celery task ID to poll.
        timeout: Maximum seconds to wait.
        compose_file: Docker compose file for log dumping on failure.

    Returns:
        The task's decoded result object, or None if it returned nothing.

    Raises:
        SystemExit: If the task fails or times out.
    """
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task_url = f"{base_url}/api/tasks/{task_id}"
        resp = httpx.get(task_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(
                f"Task poll failed ({resp.status_code}): {resp.text}", file=sys.stderr
            )
            sys.exit(1)
        data = resp.json()
        state = data.get("state", "UNKNOWN")
        if state == "SUCCESS":
            print(f"  Task {task_id[:8]}... completed")
            return data.get("result_object")
        if state in ("FAILURE", "REVOKED"):
            print(f"  Task {task_id[:8]}... failed: {data}", file=sys.stderr)
            if compose_file:
                print("  --- Celery worker logs ---", file=sys.stderr)
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        compose_file,
                        "logs",
                        "--tail=30",
                        "grampsweb_celery",
                    ],
                    timeout=10,
                )
            sys.exit(1)
        time.sleep(1)
    print(f"Task {task_id[:8]}... timed out after {timeout}s", file=sys.stderr)
    sys.exit(1)


def import_data(
    compose_file: str, base_url: str, token: str, seed_file: Path, timeout: float
) -> None:
    """
    Import the seed Gramps XML file via the Gramps Web API.

    Uploads the gzip-compressed seed file as raw binary to the import
    endpoint, polls the Celery task until completion, and checks the
    object counts the task reports against the fixture (issue #94).

    Args:
        compose_file: Path to docker-compose file.
        base_url: Gramps Web base URL.
        token: JWT access token.
        seed_file: Path to the .gramps seed file.
        timeout: Maximum seconds to wait for import completion.

    Raises:
        SystemExit: If the import fails or reports fewer objects than the fixture.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    file_bytes = seed_file.read_bytes()
    print(f"Importing {seed_file.name} ({len(file_bytes)} bytes)...")

    resp = httpx.post(
        f"{base_url}/api/importers/gramps/file",
        content=file_bytes,
        headers=headers,
        timeout=30,
    )
    if resp.status_code not in (200, 201, 202):
        print(
            f"Import request failed ({resp.status_code}): {resp.text}", file=sys.stderr
        )
        # Dump celery logs for debugging
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "logs", "grampsweb_celery"],
            timeout=10,
        )
        sys.exit(1)

    data = resp.json()
    task_id = data.get("task", {}).get("id") or data.get("task_id")
    if task_id:
        result = poll_task(base_url, token, task_id, timeout, compose_file)
    else:
        result = data  # Reason: inline import, the body holds the counts.
    shortfalls = count_shortfalls(import_counts(result))
    if shortfalls:
        print("Import task succeeded but read short of the fixture:", file=sys.stderr)
        for line in shortfalls:
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)


def rebuild_search_index(base_url: str, token: str, timeout: float) -> None:
    """
    Trigger a search index rebuild and wait for completion.

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.
        timeout: Maximum seconds to wait.

    Raises:
        SystemExit: If the rebuild fails.
    """
    headers = {"Authorization": f"Bearer {token}"}
    print("Rebuilding search index...")
    index_url = f"{base_url}/api/search/index/"
    resp = httpx.post(index_url, headers=headers, timeout=10)
    if resp.status_code not in (200, 201, 202):
        print(
            f"Index rebuild failed ({resp.status_code}): {resp.text}", file=sys.stderr
        )
        sys.exit(1)
    data = resp.json()
    task_id = data.get("task", {}).get("id") or data.get("task_id")
    if task_id:
        poll_task(base_url, token, task_id, timeout)
    else:
        print("  Index rebuild completed (synchronous)")


def import_counts(result: dict | None) -> dict[str, int]:
    """
    Pick the fixture collections' counts out of an import task result.

    gramps-webapi 3.24+ returns its dry run's counts; older ones fail closed.

    Args:
        result: The import task's result object, or None.

    Returns:
        Mapping of collection name to count, -1 when the result lacks it.
    """
    result = result or {}
    return {name: result.get(name, -1) for name in FIXTURE_COUNTS}


def count_shortfalls(observed: dict[str, int]) -> list[str]:
    """
    Compare observed collection totals against the fixture floors.

    Args:
        observed: Mapping of collection name to row count, -1 when unknown.

    Returns:
        One human-readable line per collection that is short or unreadable.
    """
    shortfalls = []
    for collection, expected in FIXTURE_COUNTS.items():
        actual = observed.get(collection, -1)
        if actual < 0:
            shortfalls.append(f"{collection}: count unavailable (expected {expected})")
        elif actual < expected:
            shortfalls.append(f"{collection}: {actual} rows, expected >= {expected}")
    return shortfalls


def count_collection(base_url: str, token: str, collection: str) -> int:
    """
    Read a collection's total row count from the X-Total-Count header.

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.
        collection: API collection segment, e.g. "people".

    Returns:
        The row count, or -1 if the API did not answer with a usable total.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = httpx.get(
            f"{base_url}/api/{collection}/?pagesize=1", headers=headers, timeout=15
        )
    except httpx.TransportError as exc:
        print(f"  {collection}: request failed ({exc})", file=sys.stderr)
        return -1
    if resp.status_code != 200:
        print(f"  {collection}: HTTP {resp.status_code}", file=sys.stderr)
        return -1
    try:
        return int(resp.headers["x-total-count"])
    except (KeyError, ValueError):
        return len(resp.json()) if isinstance(resp.json(), list) else -1


def verify_data(base_url: str, token: str) -> None:
    """
    Verify the imported tree holds at least the fixture's row counts.

    Anchor-record presence cannot tell a full import from a partial one, so
    this asserts collection totals instead (issue #91).

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.

    Raises:
        SystemExit: If any collection is short of its fixture floor.
    """
    observed = {
        collection: count_collection(base_url, token, collection)
        for collection in FIXTURE_COUNTS
    }
    shortfalls = count_shortfalls(observed)
    if shortfalls:
        print(
            "Verification failed: imported tree is short of the fixture",
            file=sys.stderr,
        )
        for line in shortfalls:
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)
    summary = ", ".join(f"{name}={observed[name]}" for name in FIXTURE_COUNTS)
    print(f"Verified fixture row counts: {summary}")


def main() -> None:
    """
    Run the full seed workflow: health check, user creation, import, index, verify.
    """
    parser = argparse.ArgumentParser(
        description="Seed a local Gramps Web test instance"
    )
    parser.add_argument("--base-url", help="Gramps Web URL (default: own test stack)")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="Owner username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Owner password")
    parser.add_argument(
        "--compose-file",
        default="docker-compose.test.yml",
        help="Path to docker-compose file",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Max seconds to wait for operations",
    )
    parser.add_argument(
        "--skip-if-seeded",
        action="store_true",
        help="Exit early if the integrity probe (I0001 + R0000) passes",
    )
    args = parser.parse_args()
    args.base_url = resolve_base_url(args.base_url)

    if not SEED_FILE.exists():
        print(f"Seed file not found: {SEED_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"Seeding Gramps Web at {args.base_url}")
    print(f"  Seed file: {SEED_FILE}")
    print()

    wait_for_healthy(args.base_url, timeout=args.timeout)
    create_user(args.compose_file, args.username, args.password, ROLE_OWNER)
    create_user(args.compose_file, EDITOR_USERNAME, EDITOR_PASSWORD, ROLE_EDITOR)
    token = authenticate(args.base_url, args.username, args.password)

    if args.skip_if_seeded and is_already_seeded(args.base_url, token):
        print("Seed data intact (I0001 + R0000 found) -- skipping import")
        return

    import_data(
        args.compose_file, args.base_url, token, SEED_FILE, timeout=args.timeout
    )
    rebuild_search_index(args.base_url, token, timeout=args.timeout)
    verify_data(args.base_url, token)

    print()
    print("Seed complete!")


if __name__ == "__main__":
    main()
