# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Overlays for the table-driven operations (#99, slice S2 #101).

``search``, ``list_tags``, ``get`` and ``delete`` are built by
``registry_build.build_registry`` from these overlays and the generated
resource table. The wording, schemas and hints here are the hand-kept
part; entity paths and verbs come from ``resource_table.ENTITY_RESOURCES``.
"""

from .models.parameters.simple_params import (
    DeletableEntityType,
    DeleteParams,
    EntityType,
    SimpleFindParams,
    SimpleGetParams,
)
from .models.parameters.tag_params import TagSearchParams
from .registry_build import OpOverlay

# Import handlers directly from sub-modules (not tools/__init__.py)
# to avoid circular imports, as operations.py does.
from .tools.data_management_delete import delete_tool
from .tools.search_basic import list_tags_tool, search_tool
from .tools.search_details import get_tool

_SEARCHABLE = tuple(e.value for e in EntityType)
_DELETABLE = tuple(e.value for e in DeletableEntityType)

TABLE_OVERLAYS: tuple[OpOverlay, ...] = (
    OpOverlay(
        name="search",
        summary=(
            "Search any entity type using GQL queries. "
            "Do NOT use 'search_person' -- use this with params.type."
        ),
        description=(
            "Search any entity type using GQL - read gql://documentation "
            "resource first to understand syntax. "
            "Key GQL property paths: "
            "People: primary_name.first_name, "
            "primary_name.surname_list[0].surname (NOT 'name'). "
            "Places: name.value (NOT 'name'), place_type.string (NOT 'type'). "
            "Events/Families/Repositories: type.string. "
            "Notes: text.string (NOT 'text'). "
            "Type-name filters are rewritten to the integer form "
            "(`.value` in place of `.string`) before querying; custom type "
            "names are not translated yet and return no results. "
            'Multi-word values MUST be quoted: name.value ~ "New York".'
        ),
        category="search",
        params_schema=SimpleFindParams,
        handler=search_tool,
        read_only=True,
        destructive=False,
        scope="collection",
        verb="GET",
        entities=_SEARCHABLE,
    ),
    OpOverlay(
        name="list_tags",
        summary="List all tags in the family tree",
        description="List all tags in the family tree",
        category="search",
        params_schema=TagSearchParams,
        handler=list_tags_tool,
        read_only=True,
        destructive=False,
        scope="collection",
        verb="GET",
        entities=("tag",),
    ),
    OpOverlay(
        name="get",
        summary=(
            "Get full details for any entity by handle or gramps_id. "
            "Pass params.type to specify the entity kind. "
            "Do NOT use 'get_person' or 'get_media' -- use 'get' with params.type."
        ),
        description=(
            "Get full details for any entity (person, family, event, place, "
            "source, citation, media, repository, note) by handle or gramps_id. "
            "Pass params.type to specify the entity kind. "
            "Do NOT use 'get_person' or 'get_media' -- use 'get' with params.type."
        ),
        category="read",
        params_schema=SimpleGetParams,
        handler=get_tool,
        read_only=True,
        destructive=False,
        scope="item",
        verb="GET",
        entities=_SEARCHABLE,
    ),
    OpOverlay(
        name="delete",
        summary=(
            "Delete any entity by type and handle. "
            "Do NOT use 'delete_person' -- use 'delete' with params.type."
        ),
        description=(
            "Delete any entity by type and handle. "
            "Do NOT use 'delete_person' -- use 'delete' with params.type."
        ),
        category="delete",
        params_schema=DeleteParams,
        handler=delete_tool,
        read_only=False,
        destructive=True,
        scope="item",
        verb="DELETE",
        entities=_DELETABLE,
    ),
)
