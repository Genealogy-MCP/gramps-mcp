# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Configuration management for Gramps MCP Server.
"""

import functools
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, ValidationError

# Load environment variables from .env file
load_dotenv()

_REQUIRED_ENV_VARS = ("GRAMPS_API_URL", "GRAMPS_USERNAME", "GRAMPS_PASSWORD")


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Gramps Web API Configuration
    gramps_api_url: HttpUrl = Field(..., description="Base URL for Gramps Web API")
    gramps_username: str = Field(..., description="Username for Gramps Web API")
    gramps_password: str = Field(..., description="Password for Gramps Web API")
    gramps_tree_id: str = Field(
        default="", description="Family tree identifier (empty = auto-discover)"
    )


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get settings from environment variables.

    Raises ValueError if any required env var is missing.
    Cached via lru_cache (MCP-23): settings are immutable after load_dotenv().
    """
    missing = [var for var in _REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in your Gramps Web credentials."
        )

    try:
        return Settings(
            gramps_api_url=HttpUrl(os.environ["GRAMPS_API_URL"]),
            gramps_username=os.environ["GRAMPS_USERNAME"],
            gramps_password=os.environ["GRAMPS_PASSWORD"],
            gramps_tree_id=os.environ.get("GRAMPS_TREE_ID", ""),
        )
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")
