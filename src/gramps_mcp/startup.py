# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Server startup initialization and validation.
"""

import logging

from .auth import GrampsAuthError
from .client import get_client
from .schema_pin import SCHEMA_VERSION
from .tools._errors import describe_auth_error

logger = logging.getLogger(__name__)


async def verify_api_on_startup() -> None:
    """Check Gramps Web API version at startup.

    Raises on unsupported (pre-3.x) versions. A login failure, including
    an unreachable server, is logged at error level with its real cause
    and the server keeps starting, so tool calls can report the same
    cause to the LLM. When the server reports
    a version other than the one the schema snapshot is pinned to, logs
    one warning and carries on: the snapshot may describe fields the
    server lacks, or miss ones it has.
    """
    try:
        version = await get_client().verify_api_version()
    except GrampsAuthError as e:
        logger.error("Startup API check failed: %s", describe_auth_error(e))
        return
    if version and version.lstrip("v") != SCHEMA_VERSION:
        logger.warning(
            "Gramps Web API %s differs from the schema snapshot pinned to %s; "
            "generated resource table may drift (run `make schema-fetch`)",
            version,
            SCHEMA_VERSION,
        )
