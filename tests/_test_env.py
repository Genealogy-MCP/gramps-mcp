# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Resolution of the Gramps test-instance environment variables.

GRAMPS_API_URL, GRAMPS_USERNAME and GRAMPS_PASSWORD address one instance, so
they are resolved as a group. A password inherited from the shell for the live
instance must not be paired with the local Docker URL: the local seed rejects
it with 403 and every integration test fails on "Invalid username or password".
"""

from typing import Dict, List, Mapping, Tuple

DEFAULT_API_URL = "http://localhost:5055"
DEFAULT_USERNAME = "owner"
DEFAULT_PASSWORD = "owner"

_CREDENTIAL_VARS = ("GRAMPS_USERNAME", "GRAMPS_PASSWORD")


def resolve_test_env(environ: Mapping[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Resolve the target instance and its credentials from an environment.

    Credentials apply only to an instance the caller named, and only as a
    complete pair. Anything else falls back to the local seed, so a live
    password inherited from the shell never reaches the local Docker URL.

    Args:
        environ: Environment mapping to read (normally os.environ).

    Returns:
        A (updates, ignored) pair. `updates` holds the variables to apply to
        the environment. `ignored` names the inherited credential variables
        that were discarded because the pair was incomplete.
    """
    updates: Dict[str, str] = {}
    named_instance = bool(environ.get("GRAMPS_API_URL"))
    if not named_instance:
        updates["GRAMPS_API_URL"] = DEFAULT_API_URL

    present = [var for var in _CREDENTIAL_VARS if environ.get(var)]
    if named_instance and len(present) == len(_CREDENTIAL_VARS):
        return updates, []

    updates["GRAMPS_USERNAME"] = DEFAULT_USERNAME
    updates["GRAMPS_PASSWORD"] = DEFAULT_PASSWORD
    return updates, present
