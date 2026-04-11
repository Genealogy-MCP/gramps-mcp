# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
MCP ``search`` meta-tool — discovers operations from the registry.

Part of the Code Mode architecture (MCP-29). The LLM calls this tool
to find which operations are available and what parameters they accept,
then calls ``execute`` to run the chosen operation.
"""

from typing import Optional

from mcp.types import TextContent
from pydantic import BaseModel, Field

from ..operations import OPERATION_REGISTRY, search_operations, summarize_params


class SearchOperationsParams(BaseModel):
    query: str = Field(
        ...,
        description=(
            "Free-text query to find operations. Examples: 'find people', "
            "'create event', 'delete', 'ancestors'. Use short keywords."
        ),
    )
    category: Optional[str] = Field(
        None,
        description=(
            "Optional filter by category: search, read, write, delete, analysis"
        ),
    )


async def search_operations_tool(arguments: dict) -> list[TextContent]:
    """Search the operation registry for matching operations.

    Returns structured text describing each matching operation, its
    category, parameters, and any token warnings.

    Args:
        arguments: Dict with 'query' and optional 'category'.

    Returns:
        List of TextContent with formatted operation descriptions.
    """
    params = SearchOperationsParams(**arguments)
    matches = search_operations(params.query, category=params.category)

    if not matches:
        all_ops = list(OPERATION_REGISTRY.values())
        lines = [
            f"No operations matched '{params.query}'. "
            f"There are {len(all_ops)} operations available:",
            "",
        ]
        for entry in all_ops:
            lines.append(f"  - {entry.name} [{entry.category}]: {entry.summary}")
        return [TextContent(type="text", text="\n".join(lines))]

    lines = [f"Found {len(matches)} matching operation(s):", ""]
    for entry in matches:
        lines.append(f"### {entry.name}  [{entry.category}]")
        lines.append(f"{entry.summary}")
        if entry.token_warning:
            lines.append(f"WARNING: {entry.token_warning}")
        lines.append("")

        param_summary = summarize_params(entry.params_schema)
        if param_summary:
            lines.append("Parameters:")
            for p in param_summary:
                req = "required" if p["required"] else "optional"
                desc = f" - {p['description']}" if p["description"] else ""
                lines.append(f"  - {p['name']} ({p['type']}, {req}){desc}")
            lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
