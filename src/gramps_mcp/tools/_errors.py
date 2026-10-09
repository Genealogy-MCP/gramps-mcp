# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Shared error handling for MCP tool responses.

MCP-8: Tool execution errors MUST be returned with isError=True so the LLM
can distinguish errors from valid data and self-correct. The MCP Server SDK
automatically sets isError=True when a tool handler raises an exception.

MCP-10: This is the single source of truth for error formatting.

McpToolError is re-exported from the shared library. raise_tool_error remains
local because it handles GrampsAPIError specifically.
"""

import difflib
import logging
from typing import NoReturn, TypeVar

from mcp_codemode import McpToolError
from pydantic import BaseModel, ValidationError

from ..client import GrampsAPIError

__all__ = [
    "McpToolError",
    "describe_validation_error",
    "parse_params",
    "raise_tool_error",
]

logger = logging.getLogger(__name__)

_ParamsT = TypeVar("_ParamsT", bound=BaseModel)


def describe_validation_error(
    error: ValidationError, model: type[BaseModel] | None = None
) -> str:
    """Render a pydantic ValidationError as an actionable message (MCP-9).

    Unknown keys get their own phrasing naming the offending key and, when the
    model is known and one of its fields is close enough to be a typo, the
    field the caller probably meant. Every other error keeps pydantic's own
    text, which is already specific about what was wrong.

    Args:
        error: The exception raised while building a parameter model.
        model: The model that rejected the input, used to suggest a near miss.

    Returns:
        str: A message telling the caller what to change.
    """
    extras = [e for e in error.errors() if e["type"] == "extra_forbidden"]
    if not extras:
        return str(error)

    known = sorted(model.model_fields) if model else []
    parts = []
    for entry in extras:
        key = str(entry["loc"][-1])
        close = difflib.get_close_matches(key, known, n=1, cutoff=0.6)
        parts.append(f"'{key}' (did you mean '{close[0]}'?)" if close else f"'{key}'")

    return (
        f"Unknown parameter(s) for {error.title}: {', '.join(parts)}. "
        f"Nothing was saved. Check the operation's accepted parameters "
        f"with search and retry."
    )


def parse_params(model: type[_ParamsT], arguments: dict) -> _ParamsT:
    """Build a parameter model, converting rejection into an LLM-readable error.

    This is the single parse boundary for write operations: it is the one place
    that knows both the model and the failure, which is what lets the message
    name the field a misspelled key probably meant.

    Args:
        model: The parameter model class to construct.
        arguments: Raw arguments supplied by the caller.

    Returns:
        The validated model instance.

    Raises:
        McpToolError: If the arguments do not satisfy the model.
    """
    try:
        return model(**arguments)
    except ValidationError as e:
        message = describe_validation_error(e, model)
        logger.error(f"Parameter validation failed for {model.__name__}: {message}")
        raise McpToolError(message) from e


def raise_tool_error(
    error: Exception,
    operation: str,
    *,
    entity_type: str | None = None,
    identifier: str | None = None,
) -> NoReturn:
    """Log and re-raise an exception as McpToolError.

    The MCP Server framework catches this and returns the message to the LLM
    with isError=True, allowing it to self-correct.

    Args:
        error: The original exception.
        operation: Human-readable description of the failed operation
            (e.g. "person search", "family save").
        entity_type: Optional entity type for context (e.g. "person").
        identifier: Optional handle or gramps_id for context.

    Raises:
        McpToolError: Always raised with a formatted error message.
    """
    if isinstance(error, GrampsAPIError):
        error_msg = str(error)
    elif isinstance(error, McpToolError):
        error_msg = str(error)
    else:
        error_msg = f"Unexpected error during {operation}: {error}"

    # MCP-9: Append entity context when available
    if entity_type and identifier:
        error_msg += f" [{entity_type}: {identifier}]"
    elif identifier:
        error_msg += f" [id: {identifier}]"

    logger.error(f"Tool error in {operation}: {error_msg}")
    raise McpToolError(error_msg) from error
