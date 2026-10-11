# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Table-driven operation registry assembly (#99, slice S2 #101).

An overlay carries what the OpenAPI snapshot cannot say: the operation
name, the LLM-facing wording, the params schema, the handler and the
behaviour hints. ``build_registry`` checks each overlay against the
generated resource table (every entity it serves must exist there and
list the verb at the right scope) and returns ``OperationEntry`` objects.
``merge_registry`` joins them with the handwritten entries.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from mcp_codemode import OperationEntry

from .resource_rows import EntityResource

_SCOPES = ("collection", "item")


@dataclass(frozen=True)
class OpOverlay:
    """Hand-kept facts for one table-driven operation.

    Attributes:
        name: Stable operation name (MCP-1).
        summary: One-line search-result text.
        description: Full LLM-facing description.
        category: Registry category label.
        params_schema: Pydantic model the execute layer validates against.
        handler: Async ``(ctx, params)`` handler.
        read_only: Behaviour hint, True when nothing is mutated.
        destructive: Behaviour hint, True when data is deleted.
        scope: ``"collection"`` or ``"item"``; which table path the op uses.
        verb: HTTP verb the op sends on that path.
        entities: Entity keys the op serves; each must be a table row.
    """

    name: str
    summary: str
    description: str
    category: str
    params_schema: type
    handler: Callable[..., Any]
    read_only: bool
    destructive: bool
    scope: str
    verb: str
    entities: tuple[str, ...]


def _check_overlay(table: Mapping[str, EntityResource], overlay: OpOverlay) -> None:
    """
    Raise when the table cannot serve an overlay.

    Args:
        table (Mapping[str, EntityResource]): Generated resource rows.
        overlay (OpOverlay): Overlay to check.

    Raises:
        ValueError: Unknown scope, unknown entity, or verb not in the row.
    """
    if overlay.scope not in _SCOPES:
        raise ValueError(
            f"Operation '{overlay.name}' has scope '{overlay.scope}'; "
            f"expected one of {', '.join(_SCOPES)}."
        )
    for entity in overlay.entities:
        row = table.get(entity)
        if row is None:
            raise ValueError(
                f"Operation '{overlay.name}' serves entity '{entity}', "
                f"which the resource table does not list."
            )
        verbs = (
            row.collection_verbs if overlay.scope == "collection" else row.item_verbs
        )
        if overlay.verb not in verbs:
            raise ValueError(
                f"Operation '{overlay.name}' sends {overlay.verb} on the "
                f"{entity} {overlay.scope} path, but the table lists only "
                f"{', '.join(verbs)}."
            )


def build_registry(
    table: Mapping[str, EntityResource], overlays: Iterable[OpOverlay]
) -> dict[str, OperationEntry]:
    """
    Build registry entries from the resource table and overlays.

    Args:
        table (Mapping[str, EntityResource]): Generated resource rows.
        overlays (Iterable[OpOverlay]): One overlay per operation.

    Returns:
        dict[str, OperationEntry]: Entries keyed by operation name, in
            overlay order.

    Raises:
        ValueError: An overlay the table cannot serve, or a duplicate name.
    """
    registry: dict[str, OperationEntry] = {}
    for overlay in overlays:
        _check_overlay(table, overlay)
        if overlay.name in registry:
            raise ValueError(f"Duplicate table operation name '{overlay.name}'.")
        registry[overlay.name] = OperationEntry(
            name=overlay.name,
            summary=overlay.summary,
            description=overlay.description,
            category=overlay.category,
            params_schema=overlay.params_schema,
            handler=overlay.handler,
            read_only=overlay.read_only,
            destructive=overlay.destructive,
        )
    return registry


def merge_registry(
    handwritten: Mapping[str, OperationEntry],
    generated: Mapping[str, OperationEntry],
    order: Sequence[str],
) -> dict[str, OperationEntry]:
    """
    Join handwritten and table-built entries into one ordered registry.

    Reason: the ``search`` meta-tool lists operations in registry order
    for an empty query, so the merged order is pinned explicitly.

    Args:
        handwritten (Mapping[str, OperationEntry]): Hand-kept entries.
        generated (Mapping[str, OperationEntry]): ``build_registry`` output.
        order (Sequence[str]): Every operation name, in listing order.

    Returns:
        dict[str, OperationEntry]: The merged registry.

    Raises:
        ValueError: A name in both halves, or an order list that does not
            name exactly the merged operations.
    """
    collisions = sorted(set(handwritten) & set(generated))
    if collisions:
        raise ValueError(
            f"Operation names defined twice (handwritten and table): "
            f"{', '.join(collisions)}."
        )
    merged = {**handwritten, **generated}
    if len(order) != len(set(order)) or set(order) != set(merged):
        missing = sorted(set(merged) - set(order))
        extra = sorted(set(order) - set(merged))
        raise ValueError(
            f"Registry order does not match the operations: "
            f"missing {missing}, unknown {extra}."
        )
    return {name: merged[name] for name in order}
