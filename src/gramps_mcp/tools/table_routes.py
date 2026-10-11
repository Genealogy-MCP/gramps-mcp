# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Endpoint lookups and read overlays driven by the resource table (#101).

The generated ``ENTITY_RESOURCES`` table owns every entity path and verb.
``collection_call`` and ``item_call`` turn a table row into the client's
``ApiCalls`` key, so the read and delete handlers never name a per-entity
endpoint. ``READ_OVERLAYS`` keeps what the table cannot know: the search
params class, the display label used in messages and GQL hints, and the
formatter.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ..handlers.citation_handler import format_citation
from ..handlers.event_handler import format_event
from ..handlers.family_handler import format_family
from ..handlers.media_handler import format_media
from ..handlers.note_handler import format_note
from ..handlers.person_handler import format_person
from ..handlers.place_handler import format_place
from ..handlers.repository_handler import format_repository
from ..handlers.source_handler import format_source
from ..models.api_calls import ApiCalls
from ..models.parameters.base_params import BaseGetMultipleParams
from ..models.parameters.citation_params import GetCitationsParams
from ..models.parameters.event_params import EventSearchParams
from ..models.parameters.media_params import MediaSearchParams
from ..models.parameters.note_params import NotesParams
from ..models.parameters.place_params import PlaceSearchParams
from ..models.parameters.repository_params import RepositoriesParams
from ..models.parameters.source_params import SourceSearchParams
from ..resource_rows import EntityResource
from ..resource_table import ENTITY_RESOURCES


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
    """

    params_class: type
    label: str
    formatter: Callable
    empty_detail: str = ""


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
    "note": ReadOverlay(NotesParams, "notes", format_note),
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


def _to_api_call(verb: str, path: str, entity: str, verbs: tuple) -> ApiCalls:
    """
    Map a table verb and path to the client's ApiCalls key.

    Args:
        verb (str): HTTP verb.
        path (str): Path template from the table row.
        entity (str): Entity key, for the error message.
        verbs (tuple): Verbs the table lists on that path.

    Returns:
        ApiCalls: The member whose value is ``(verb, path)``.

    Raises:
        ValueError: The table does not list the verb on that path.
    """
    if verb not in verbs:
        raise ValueError(
            f"The resource table lists {', '.join(verbs)} on {path} "
            f"({entity}), not {verb}."
        )
    return ApiCalls((verb, path))


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
    return _to_api_call(verb, row.collection_path, entity, row.collection_verbs)


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
    return _to_api_call(verb, row.item_path, entity, row.item_verbs)


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
