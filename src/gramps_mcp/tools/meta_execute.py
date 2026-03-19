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
MCP ``execute`` meta-tool — runs a validated operation from the registry.

Part of the Code Mode architecture (MCP-29). The LLM discovers operations
via ``search``, then calls this tool to run one. Each operation is validated
via its Pydantic schema before dispatching to the existing handler.
"""

import difflib

from mcp.types import TextContent
from pydantic import BaseModel, Field

from ..operations import OPERATION_REGISTRY
from ._errors import McpToolError


class ExecuteOperationParams(BaseModel):
    operation: str = Field(
        ...,
        description=(
            "Name of the operation to run. Use the 'search' meta-tool first "
            "to discover available operations and their parameters."
        ),
    )
    params: dict = Field(
        default_factory=dict,
        description="Parameters for the operation (see operation schema).",
    )


async def execute_operation_tool(arguments: dict) -> list[TextContent]:
    """Execute a named operation from the registry.

    Validates the operation name, then dispatches to the registered
    handler with the provided parameters.

    Args:
        arguments: Dict with 'operation' and 'params'.

    Returns:
        List of TextContent from the operation handler.

    Raises:
        McpToolError: If the operation is unknown (includes suggestions).
    """
    validated = ExecuteOperationParams(**arguments)

    entry = OPERATION_REGISTRY.get(validated.operation)
    if entry is None:
        close = difflib.get_close_matches(
            validated.operation,
            OPERATION_REGISTRY.keys(),
            n=3,
            cutoff=0.4,
        )
        suggestion = ""
        if close:
            suggestion = f" Did you mean: {', '.join(close)}?"
        raise McpToolError(
            f"Unknown operation '{validated.operation}'.{suggestion} "
            f"Use the 'search' tool to discover available operations."
        )

    return await entry.handler(validated.params)
