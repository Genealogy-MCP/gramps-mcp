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
import re

from mcp.types import TextContent
from pydantic import BaseModel, Field

from ..operations import OPERATION_REGISTRY
from ._errors import McpToolError

_GRAMPS_ID_PATTERN = re.compile(r"^[A-Za-z]\d+$")


def _normalize_identifier(params: dict, params_schema: type) -> dict:
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
        attempted = validated.operation
        close = difflib.get_close_matches(
            attempted,
            OPERATION_REGISTRY.keys(),
            n=3,
            cutoff=0.4,
        )
        # Catch per-type names like "get_media" -> suggest "get"
        prefix_matches = [
            name
            for name in OPERATION_REGISTRY
            if attempted.startswith(name + "_") and name not in close
        ]
        all_suggestions = close + prefix_matches
        suggestion = ""
        if all_suggestions:
            suggestion = f" Did you mean: {', '.join(all_suggestions)}?"
        raise McpToolError(
            f"Unknown operation '{attempted}'.{suggestion} "
            f"Use the 'search' tool to discover available operations."
        )

    normalized = _normalize_identifier(validated.params, entry.params_schema)
    return await entry.handler(normalized)
