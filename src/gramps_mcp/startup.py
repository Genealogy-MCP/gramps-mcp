# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Server startup initialization and validation.
"""

from .client import GrampsWebAPIClient


async def verify_api_on_startup() -> None:
    """Check Gramps Web API version at startup.

    Logs the result and raises on unsupported versions.
    Gracefully degrades on connection errors (the check is best-effort
    at startup — tool calls will surface auth/connection errors later).
    """
    client = GrampsWebAPIClient()
    try:
        await client.verify_api_version()
    finally:
        await client.close()
