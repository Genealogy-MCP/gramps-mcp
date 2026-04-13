# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Identifier normalization for Gramps MCP operations.

Maps LLM-invented 'identifier' param to the correct schema field
(handle or gramps_id) based on value format and schema introspection.
"""

import re

_GRAMPS_ID_PATTERN = re.compile(r"^[A-Za-z]\d+$")


def normalize_identifier(params: dict, params_schema: type) -> dict:
    """Map LLM-invented 'identifier' to the correct schema field.

    LLMs sometimes pass 'identifier' instead of 'handle' or 'gramps_id'.
    This normalizes based on value format and schema introspection.
    Does nothing if handle or gramps_id is already set.

    Args:
        params: Mutable dict of operation parameters.
        params_schema: Pydantic model class for the target operation.

    Returns:
        The same dict, mutated in place.
    """
    if "identifier" not in params:
        return params

    if params.get("handle") or params.get("gramps_id"):
        params.pop("identifier")
        return params

    schema_fields = params_schema.model_fields
    has_handle = "handle" in schema_fields
    has_gramps_id = "gramps_id" in schema_fields

    identifier = params.pop("identifier")

    if _GRAMPS_ID_PATTERN.match(str(identifier)) and has_gramps_id:
        params["gramps_id"] = identifier
    elif has_handle:
        params["handle"] = identifier
    elif has_gramps_id:
        params["gramps_id"] = identifier

    return params
