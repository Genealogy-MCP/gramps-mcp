# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Compatibility shim for the mcp-codemode handler calling convention.

The library calls handlers as handler(ctx, validated_params) where
validated_params is a Pydantic model. Legacy callers (tests, internal
dispatch) pass a plain dict. This module provides a helper to extract
the arguments dict from either calling convention.
"""

from typing import Any


def extract_arguments(ctx_or_args: Any = None, params: Any = None) -> dict:
    """Extract a plain dict from either library or legacy calling convention.

    Library convention: handler(ctx, pydantic_model)
    Legacy convention: handler(plain_dict)

    Args:
        ctx_or_args: MCP context (library) or plain dict (legacy).
        params: Pydantic model with model_dump() (library) or None (legacy).

    Returns:
        A plain dict of operation arguments.
    """
    if params is not None and hasattr(params, "model_dump"):
        return params.model_dump(mode="json", exclude_none=True)
    if isinstance(ctx_or_args, dict):
        return ctx_or_args
    return {}
