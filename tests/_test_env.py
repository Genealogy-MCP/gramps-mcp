# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Resolution of the Gramps test-instance environment variables.

GRAMPS_API_URL, GRAMPS_USERNAME and GRAMPS_PASSWORD address one instance, so
they are resolved as a group. A password inherited from the shell for the live
instance must not be paired with the local Docker URL: the local seed rejects
it with 403 and every integration test fails on "Invalid username or password".

The local Docker instance has no fixed address. docker-compose.test.yml
publishes grampsweb on an ephemeral host port, so every checkout's compose
project gets its own port and parallel worktrees never share an instance
(issue #124). The URL is read back from Docker with `docker compose port`.
"""

import logging
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "docker-compose.test.yml"

# Reason: with no stack of its own running, the suite must not fall back to a
# fixed port that another checkout's stack may hold. Nothing listens on the
# discard port, so integration tests skip (or fail under REQUIRE_INTEGRATION).
UNREACHABLE_API_URL = "http://127.0.0.1:9"

DEFAULT_USERNAME = "owner"
DEFAULT_PASSWORD = "owner"

# Editor-role account the seed script provisions next to the owner. Editors
# lack the ManageBackups permission, so permission-error tests log in as it.
EDITOR_USERNAME = "editor"
EDITOR_PASSWORD = "editor"

_CREDENTIAL_VARS = ("GRAMPS_USERNAME", "GRAMPS_PASSWORD")


def parse_published_url(port_output: str) -> Optional[str]:
    """Turn `docker compose port` output into a base URL.

    Args:
        port_output: Command stdout, e.g. "127.0.0.1:54321\\n".

    Returns:
        The base URL, or None when the output names no published port.
    """
    host, _, port = port_output.strip().rpartition(":")
    if not host or not port.isdigit() or port == "0":
        return None
    return f"http://{host}:{port}"


def local_api_url() -> Optional[str]:
    """Return the URL of this checkout's own Gramps Web test container.

    The compose project is derived from the compose file's directory (or
    COMPOSE_PROJECT_NAME), so the lookup only ever finds this checkout's
    stack, never another worktree's.

    Returns:
        The base URL, or None when Docker or the grampsweb container is down.
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "port", "grampsweb", "5000"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("docker compose port failed: %s", exc)
        return None
    if result.returncode != 0:
        return None
    return parse_published_url(result.stdout)


def resolve_base_url(base_url: Optional[str]) -> str:
    """
    Return the given URL, or this checkout's own Docker test instance URL.

    Args:
        base_url: URL passed on the command line, or None.

    Returns:
        The Gramps Web base URL to use.

    Raises:
        SystemExit: If no URL was given and the stack is not running. Its
            message goes to stderr and the script exits 1.
    """
    if base_url:
        return base_url
    discovered = local_api_url()
    if discovered is None:
        raise SystemExit(
            "This checkout's grampsweb container is not running, so it has no "
            "published port. Start it with `make docker-up`, or pass --base-url."
        )
    return discovered


def resolve_test_env(
    environ: Mapping[str, str], discover: Callable[[], Optional[str]]
) -> Tuple[Dict[str, str], List[str]]:
    """Resolve the target instance and its credentials from an environment.

    Credentials apply only to an instance the caller named, and only as a
    complete pair. Anything else falls back to the local seed, so a live
    password inherited from the shell never reaches the local Docker URL.

    Args:
        environ: Environment mapping to read (normally os.environ).
        discover: Returns this checkout's local stack URL, or None. Called
            only when environ names no instance.

    Returns:
        A (updates, ignored) pair. `updates` holds the variables to apply to
        the environment. `ignored` names the inherited credential variables
        that were discarded because the pair was incomplete.
    """
    updates: Dict[str, str] = {}
    named_instance = bool(environ.get("GRAMPS_API_URL"))
    if not named_instance:
        updates["GRAMPS_API_URL"] = discover() or UNREACHABLE_API_URL

    present = [var for var in _CREDENTIAL_VARS if environ.get(var)]
    if named_instance and len(present) == len(_CREDENTIAL_VARS):
        return updates, []

    updates["GRAMPS_USERNAME"] = DEFAULT_USERNAME
    updates["GRAMPS_PASSWORD"] = DEFAULT_PASSWORD
    return updates, present
