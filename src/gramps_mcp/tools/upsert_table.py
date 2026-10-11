# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Generic table-driven upsert handler (#102, slice S3 of #99).

Event, place, source and note save through ``upsert_entity``. The
entity's ``WriteBinding`` (``overlays.WRITE_BINDINGS``) names the hand
model and hooks; the resource table row names the paths. The order is
fixed: parse, reference checks, then the write (the client does the
merge-mode GET and merge before a PUT), then the media upload. Nothing is
written before every reference check passes.
"""

from collections.abc import Callable, Coroutine, Mapping
from typing import Any, List

from mcp.types import TextContent

from ..client import GrampsWebAPIClient
from ..config import get_settings
from ..overlays import WRITE_BINDINGS, WriteBinding, write_row
from ..resource_rows import EntityResource
from ..resource_table import ENTITY_RESOURCES
from ._compat import extract_arguments
from ._data_helpers import _extract_entity_data, _format_save_response
from ._errors import McpToolError, parse_params, raise_tool_error

UpsertHandler = Callable[..., Coroutine[Any, Any, List[TextContent]]]


async def upsert_entity(
    entity: str,
    arguments: Any,
    bindings: Mapping[str, WriteBinding] = WRITE_BINDINGS,
    table: Mapping[str, EntityResource] = ENTITY_RESOURCES,
) -> List[TextContent]:
    """
    Create or update one record of a table-driven entity.

    Args:
        entity (str): Entity key bound in ``bindings``.
        arguments (Any): Raw arguments dict, or an already parsed model.
        bindings (Mapping[str, WriteBinding]): Per-entity write bindings.
        table (Mapping[str, EntityResource]): Resource rows.

    Returns:
        List[TextContent]: The formatted save confirmation.

    Raises:
        McpToolError: Invalid arguments, a failed reference check, or a
            failed API call (with "<entity> save" context).
    """
    binding = bindings[entity]
    try:
        # Reason: the hand model is the only parse boundary; the table's
        # field set never filters, adds or forwards a field.
        validated: Any = (
            arguments
            if isinstance(arguments, binding.model)
            else parse_params(
                binding.model, arguments if isinstance(arguments, dict) else {}
            )
        )
        row = write_row(entity, table)
        tree_id = get_settings().gramps_tree_id

        client = GrampsWebAPIClient()
        try:
            for check in binding.reference_checks:
                await check(client, tree_id, validated)

            if validated.handle:
                result = await client.call_resource(
                    "PUT",
                    row.item_path,
                    validated,
                    tree_id=tree_id,
                    handle=validated.handle,
                )
                operation = "updated"
            else:
                result = await client.call_resource(
                    "POST", row.collection_path, validated, tree_id=tree_id
                )
                operation = "created"

            if binding.media_upload is not None:
                await binding.media_upload(client, tree_id, validated)

            nudge = (
                binding.nudge_citation
                and operation == "created"
                and not getattr(validated, "citation_list", None)
            )
            entity_data = _extract_entity_data(result, entity)
            text = await _format_save_response(
                client, entity_data, entity, operation, tree_id, nudge
            )
            return [TextContent(type="text", text=text)]
        finally:
            await client.close()

    except McpToolError:
        raise
    except Exception as e:
        raise_tool_error(e, f"{entity} save")


def make_upsert_handler(entity: str) -> UpsertHandler:
    """
    Build the ``(ctx, params)`` operation handler for one entity.

    Args:
        entity (str): Entity key bound in ``WRITE_BINDINGS``.

    Returns:
        UpsertHandler: Async handler the execute meta-tool dispatches to.
    """

    async def handler(ctx: Any = None, params: Any = None) -> List[TextContent]:
        """
        Create or update one record through the generic upsert.

        Args:
            ctx (Any): Operation context, or legacy arguments dict.
            params (Any): Arguments dict or parsed model.

        Returns:
            List[TextContent]: The formatted save confirmation.
        """
        return await upsert_entity(entity, extract_arguments(ctx, params))

    handler.__name__ = f"upsert_{entity}_tool"
    handler.__qualname__ = handler.__name__
    return handler


UPSERT_HANDLERS: dict[str, UpsertHandler] = {
    entity: make_upsert_handler(entity) for entity in WRITE_BINDINGS
}
