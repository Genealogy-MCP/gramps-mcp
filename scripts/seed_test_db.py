#!/usr/bin/env python3
# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 Federico Ariel Castagnini
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
Seed a local Gramps Web Docker instance with test data.

Waits for the service to be healthy, creates an owner user, imports
the vendored seed.gramps fixture, and rebuilds the search index.

Usage:
    python scripts/seed_test_db.py [--base-url URL] [--timeout SECONDS]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

SEED_FILE = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "seed.gramps"
)
DEFAULT_BASE_URL = "http://localhost:5055"
DEFAULT_USERNAME = "owner"
DEFAULT_PASSWORD = "owner"
DEFAULT_TIMEOUT = 120


def wait_for_healthy(base_url: str, timeout: float) -> None:
    """
    Poll the root URL until the service responds with HTTP 200.

    Args:
        base_url: Gramps Web base URL (e.g. http://localhost:5055).
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


def create_owner(compose_file: str, username: str, password: str) -> None:
    """
    Create the owner user via docker compose exec.

    The Gramps Web API does not expose a reliable user-creation endpoint,
    so we use the CLI inside the container.

    Args:
        compose_file: Path to docker-compose.test.yml.
        username: Owner username.
        password: Owner password.
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
            "4",
            "--email",
            f"{username}@test.com",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "already exists" in stderr.lower() or "unique constraint" in stderr.lower():
            print(f"User '{username}' already exists (OK for reruns)")
            return
        print(f"Failed to create user: {stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Created owner user '{username}'")


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


def poll_task(base_url: str, token: str, task_id: str, timeout: float) -> None:
    """
    Poll a Celery task until it reaches a terminal state.

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.
        task_id: Celery task ID to poll.
        timeout: Maximum seconds to wait.

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
            return
        if state in ("FAILURE", "REVOKED"):
            print(f"  Task {task_id[:8]}... failed: {data}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
    print(f"Task {task_id[:8]}... timed out after {timeout}s", file=sys.stderr)
    sys.exit(1)


def import_data(base_url: str, token: str, seed_file: Path, timeout: float) -> None:
    """
    Import the seed Gramps XML file via raw binary upload.

    The Gramps Web import API reads request.stream directly (not multipart).

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.
        seed_file: Path to the .gramps seed file.
        timeout: Maximum seconds to wait for import completion.

    Raises:
        SystemExit: If the import fails.
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
    if resp.status_code not in (200, 201):
        print(
            f"Import request failed ({resp.status_code}): {resp.text}", file=sys.stderr
        )
        sys.exit(1)
    data = resp.json()
    task_id = data.get("task", {}).get("id") or data.get("task_id")
    if task_id:
        poll_task(base_url, token, task_id, timeout)
    else:
        print("  Import completed (synchronous)")


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
    if resp.status_code not in (200, 201):
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


def verify_data(base_url: str, token: str) -> None:
    """
    Verify the seed data is queryable by fetching person I0001.

    Args:
        base_url: Gramps Web base URL.
        token: JWT access token.

    Raises:
        SystemExit: If verification fails.
    """
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(
        f"{base_url}/api/people/?gramps_id=I0001",
        headers=headers,
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"Verification failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    if not data:
        print(
            "Verification failed: person I0001 not found after import", file=sys.stderr
        )
        sys.exit(1)
    print(f"Verified: person I0001 found ({len(data)} result(s))")


def main() -> None:
    """
    Run the full seed workflow: health check, user creation, import, index, verify.
    """
    parser = argparse.ArgumentParser(
        description="Seed a local Gramps Web test instance"
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Gramps Web URL")
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
    args = parser.parse_args()

    if not SEED_FILE.exists():
        print(f"Seed file not found: {SEED_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"Seeding Gramps Web at {args.base_url}")
    print(f"  Seed file: {SEED_FILE}")
    print()

    wait_for_healthy(args.base_url, timeout=args.timeout)
    create_owner(args.compose_file, args.username, args.password)
    token = authenticate(args.base_url, args.username, args.password)
    import_data(args.base_url, token, SEED_FILE, timeout=args.timeout)
    rebuild_search_index(args.base_url, token, timeout=60)
    verify_data(args.base_url, token)

    print()
    print("Seed complete!")


if __name__ == "__main__":
    main()
