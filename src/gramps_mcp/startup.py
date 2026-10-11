# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Server startup initialization and validation.
"""

import logging

from .client import GrampsWebAPIClient
from .schema_pin import SCHEMA_VERSION

logger = logging.getLogger(__name__)


async def verify_api_on_startup() -> None:
    """Check Gramps Web API version at startup.

    Raises on unsupported (pre-3.x) versions. Gracefully degrades on
    connection errors (the check is best-effort at startup; tool calls
    will surface auth/connection errors later). When the server reports
    a version other than the one the schema snapshot is pinned to, logs
    one warning and carries on: the snapshot may describe fields the
    server lacks, or miss ones it has.
    """
    client = GrampsWebAPIClient()
    try:
        version = await client.verify_api_version()
    finally:
        await client.close()
    if version and version.lstrip("v") != SCHEMA_VERSION:
        logger.warning(
            "Gramps Web API %s differs from the schema snapshot pinned to %s; "
            "generated resource table may drift (run `make schema-fetch`)",
            version,
            SCHEMA_VERSION,
        )
