# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2026 Federico Castagnini
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
Shared error handling for MCP tool responses.

MCP-8: Tool execution errors MUST be returned with isError=True so the LLM
can distinguish errors from valid data and self-correct. The MCP Server SDK
automatically sets isError=True when a tool handler raises an exception.

MCP-10: This is the single source of truth for error formatting.
"""

import logging
from typing import NoReturn

from ..client import GrampsAPIError

logger = logging.getLogger(__name__)


class McpToolError(Exception):
    """Raised by tool handlers to signal an error to the LLM.

    The MCP Server SDK catches exceptions from tool handlers and wraps them
    in CallToolResult with isError=True. This exception provides a clean,
    user-facing error message for that purpose.
    """


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
