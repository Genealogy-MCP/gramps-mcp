# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Hand-kept policy for the table-driven operations (#99, #101, #102).

The generated ``resource_table.ENTITY_RESOURCES`` owns every entity path,
verb and writable field. This module keeps what the OpenAPI snapshot
cannot say, as named per-entity bindings:

* Read side: ``READ_OVERLAYS`` (search params class, display label,
  formatter) and the ``collection_call`` / ``item_call`` lookups that turn
  a table row into the client's ``ApiCalls`` key.
* Operation overlays: ``table_overlays()`` for search, list_tags, get and
  delete.

The write side (bindings, drift allowlist, upsert overlays) lives in
``write_overlays.py``.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .handlers.citation_handler import format_citation
from .handlers.event_handler import format_event
from .handlers.family_handler import format_family
from .handlers.media_handler import format_media
from .handlers.note_handler import (
    MAX_NOTE_PREVIEW_LENGTH,
    format_note,
    format_note_summary,
)
from .handlers.person_handler import format_person
from .handlers.place_handler import format_place
from .handlers.repository_handler import format_repository
from .handlers.source_handler import format_source
from .models.api_calls import ApiCalls
from .models.parameters.base_params import BaseGetMultipleParams
from .models.parameters.citation_params import GetCitationsParams
from .models.parameters.event_params import EventSearchParams
from .models.parameters.media_params import MediaSearchParams
from .models.parameters.note_params import NotesParams
from .models.parameters.place_params import PlaceSearchParams
from .models.parameters.repository_params import RepositoriesParams
from .models.parameters.simple_params import (
    DeletableEntityType,
    DeleteParams,
    EntityType,
    SimpleFindParams,
    SimpleGetParams,
)
from .models.parameters.source_params import SourceSearchParams
from .models.parameters.tag_params import TagSearchParams
from .registry_build import OpOverlay
from .resource_rows import EntityResource
from .resource_table import ENTITY_RESOURCES

# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadOverlay:
    """Hand-kept read facts for one searchable entity.

    Attributes:
        params_class: Pydantic model for the list query; its fields must
            be list params of the table row.
        label: Plural display label used in messages, GQL hints and the
            typed-enum rewrite (``"people"``, ``"media files"``, ...).
        formatter: Async ``(client, tree_id, handle)`` summary formatter.
        empty_detail: Text ``get`` shows when the formatter returns "".
        detail_formatter: Async formatter ``get`` uses when the summary
            leaves content out, or None to use ``formatter``.
    """

    params_class: type
    label: str
    formatter: Callable
    empty_detail: str = ""
    detail_formatter: Callable | None = None


# Entity -> read overlay. Person and family get their detail formatters
# (timeline join) in search_details; the summary formatter here is for
# search results.
READ_OVERLAYS: dict[str, ReadOverlay] = {
    "person": ReadOverlay(BaseGetMultipleParams, "people", format_person),
    "family": ReadOverlay(BaseGetMultipleParams, "families", format_family),
    "event": ReadOverlay(
        EventSearchParams, "events", format_event, "No event data found."
    ),
    "place": ReadOverlay(PlaceSearchParams, "places", format_place),
    "source": ReadOverlay(SourceSearchParams, "sources", format_source),
    "repository": ReadOverlay(RepositoriesParams, "repositories", format_repository),
    "media": ReadOverlay(MediaSearchParams, "media files", format_media),
    "citation": ReadOverlay(GetCitationsParams, "citations", format_citation),
    "note": ReadOverlay(
        NotesParams, "notes", format_note_summary, detail_formatter=format_note
    ),
}


def _row(entity: str, table: Mapping[str, EntityResource]) -> EntityResource:
    """
    Return the table row for an entity.

    Args:
        entity (str): Entity key (``"person"``, ``"tag"``, ...).
        table (Mapping[str, EntityResource]): Resource rows.

    Returns:
        EntityResource: The row.

    Raises:
        ValueError: The table has no row for the entity.
    """
    row = table.get(entity)
    if row is None:
        raise ValueError(f"Entity '{entity}' is not in the resource table.")
    return row


def _check_verb(verb: str, path: str, entity: str, verbs: tuple) -> None:
    """
    Raise when the table does not list a verb on a path.

    Args:
        verb (str): HTTP verb.
        path (str): Path template from the table row.
        entity (str): Entity key, for the error message.
        verbs (tuple): Verbs the table lists on that path.

    Raises:
        ValueError: The verb is not listed.
    """
    if verb not in verbs:
        raise ValueError(
            f"The resource table lists {', '.join(verbs)} on {path} "
            f"({entity}), not {verb}."
        )


def collection_call(
    entity: str,
    verb: str = "GET",
    table: Mapping[str, EntityResource] = ENTITY_RESOURCES,
) -> ApiCalls:
    """
    Resolve the collection endpoint for an entity from the table.

    Args:
        entity (str): Entity key.
        verb (str): HTTP verb; defaults to GET (list).
        table (Mapping[str, EntityResource]): Resource rows.

    Returns:
        ApiCalls: Client key for the collection path.

    Raises:
        ValueError: Unknown entity or verb not listed on the path.
    """
    row = _row(entity, table)
    _check_verb(verb, row.collection_path, entity, row.collection_verbs)
    return ApiCalls((verb, row.collection_path))


def item_call(
    entity: str,
    verb: str,
    table: Mapping[str, EntityResource] = ENTITY_RESOURCES,
) -> ApiCalls:
    """
    Resolve the single-item endpoint for an entity from the table.

    Args:
        entity (str): Entity key.
        verb (str): HTTP verb.
        table (Mapping[str, EntityResource]): Resource rows.

    Returns:
        ApiCalls: Client key for the item path.

    Raises:
        ValueError: Unknown entity or verb not listed on the path.
    """
    row = _row(entity, table)
    _check_verb(verb, row.item_path, entity, row.item_verbs)
    return ApiCalls((verb, row.item_path))


def check_list_params(
    params_class: type,
    entity: str,
    table: Mapping[str, EntityResource] = ENTITY_RESOURCES,
) -> None:
    """
    Raise when a list params class has a field the table does not list.

    Args:
        params_class (type): Pydantic model sent as list query params.
        entity (str): Entity key.
        table (Mapping[str, EntityResource]): Resource rows.

    Raises:
        ValueError: A field is not a list param of the entity's row.
    """
    allowed = {param.name for param in _row(entity, table).list_params}
    unknown = sorted(set(params_class.model_fields) - allowed)
    if unknown:
        raise ValueError(
            f"{params_class.__name__} sends {', '.join(unknown)} to the "
            f"{entity} list endpoint, which the resource table does not list."
        )


def read_route(entity: str) -> tuple[type, ApiCalls]:
    """
    Return the checked (params class, list endpoint) pair for an entity.

    Args:
        entity (str): Key of ``READ_OVERLAYS``.

    Returns:
        tuple[type, ApiCalls]: Params class and list endpoint.

    Raises:
        ValueError: The params class does not fit the table row.
    """
    params_class = READ_OVERLAYS[entity].params_class
    check_list_params(params_class, entity)
    return params_class, collection_call(entity)


# ---------------------------------------------------------------------------
# Operation overlays
# ---------------------------------------------------------------------------

_SEARCHABLE = tuple(e.value for e in EntityType)
_DELETABLE = tuple(e.value for e in DeletableEntityType)


def table_overlays() -> tuple[OpOverlay, ...]:
    """
    Return the overlays for search, list_tags, get and delete.

    Reason: handlers are imported here, not at module level, because the
    tools modules import the read lookups from this module.

    Returns:
        tuple[OpOverlay, ...]: One overlay per table-driven read/delete op.
    """
    from .tools.data_management_delete import delete_tool
    from .tools.search_basic import list_tags_tool, search_tool
    from .tools.search_details import get_tool

    return (
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
                f"Note text over {MAX_NOTE_PREVIEW_LENGTH} characters is cut; "
                "the result then has truncated: true and full_length. Use get "
                "for the whole text, always before editing a note. "
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
            summary="List the tags in the family tree",
            description=(
                "List the tags in the family tree by name. Use it to find a "
                "tag's handle or to check that a tag exists before creating "
                "it. Returns one page, 100 tags by default and at most 100, "
                "and names the next page when more tags exist."
            ),
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
                "Do NOT use 'get_person' or 'get_media' -- use 'get' with "
                "params.type."
            ),
            description=(
                "Get full details for any entity (person, family, event, place, "
                "source, citation, media, repository, note) by handle or "
                "gramps_id. Pass params.type to specify the entity kind. "
                "Do NOT use 'get_person' or 'get_media' -- use 'get' with "
                "params.type."
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
