# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Row types of the generated resource table.

`resource_table.py` is generated from the schema snapshot and instantiates
these types only; it carries no logic. Keeping the types here lets the
generated module stay pure data and lets the generic handlers (later
slices) import the shapes without importing the generator.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class FieldSpec:
    """A writable field of an entity, as the snapshot component declares it.

    `type` is a compact rendering of the OpenAPI schema: a primitive name
    (`string`, `integer`, `number`, `boolean`, `object`), a component name
    for a `$ref` (`Date`), `array[<item>]` for arrays, or `any` when the
    snapshot gives no type.
    """

    name: str
    type: str


@dataclass(frozen=True)
class ListParam:
    """A query parameter accepted by the entity's list (collection GET)."""

    name: str
    type: str


@dataclass(frozen=True)
class EntityResource:
    """One Gramps entity as the API exposes it.

    Paths are relative to the API root, in the form the client already
    uses (`people/`, `people/{handle}`).
    """

    entity: str
    component: str
    collection_path: str
    item_path: str
    collection_verbs: Tuple[str, ...]
    item_verbs: Tuple[str, ...]
    list_params: Tuple[ListParam, ...]
    fields: Tuple[FieldSpec, ...]
