# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Hand-kept write policy for the generic upsert (#102, #103).

Split from ``overlays.py`` (read side and read/delete operation overlays)
to keep both under the file-size limit. This module holds:

* ``WRITE_BINDINGS``: per entity, the hand model, citation nudge and the
  hooks the generic upsert runs (reference checks, media upload, response
  formatter), for all ten writable entities.
* ``PAYLOAD_ONLY_FIELDS`` and ``ROUTING_FIELDS``: the drift-test allowlist.
* ``upsert_overlays()``: one operation overlay per upsert.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .models.parameters.citation_params import CitationData
from .models.parameters.event_params import EventSaveParams
from .models.parameters.family_params import FamilySaveParams
from .models.parameters.media_params import MediaSaveParams
from .models.parameters.note_params import NoteSaveParams
from .models.parameters.people_params import PersonData
from .models.parameters.place_params import PlaceSaveParams
from .models.parameters.repository_params import RepositoryData
from .models.parameters.source_params import SourceSaveParams
from .models.parameters.tag_params import TagSaveParams
from .overlays import _check_verb, _row
from .registry_build import OpOverlay
from .resource_rows import EntityResource
from .resource_table import ENTITY_RESOURCES
from .write_hooks import (
    check_citation_source,
    check_note_text,
    check_person_refs,
    format_tag_save,
    has_event_refs,
    upload_media,
)

# Fields that pick the target record rather than describe it. ``handle``
# chooses PUT on the item path over POST on the collection path.
ROUTING_FIELDS: tuple[str, ...] = ("handle",)

# (hand model, field) pairs a model declares although the table does not
# list them. Each one must be consumed by the model's payload hook (or by
# ``_request_body.api_body``) so it never reaches the request body; the drift
# unit test enforces both halves.
_LIST_MODE_MODELS = (
    PersonData,
    FamilySaveParams,
    EventSaveParams,
    PlaceSaveParams,
    SourceSaveParams,
    CitationData,
    NoteSaveParams,
    RepositoryData,
    MediaSaveParams,
)
PAYLOAD_ONLY_FIELDS: tuple[tuple[type, str], ...] = (
    *((model, "list_mode") for model in _LIST_MODE_MODELS),
    (PlaceSaveParams, "enclosed_by"),
    (FamilySaveParams, "child_handles"),
    (FamilySaveParams, "family_type"),
    (MediaSaveParams, "file_location"),
)

# Async ``(client, tree_id, params)`` hook run before the write.
WriteHook = Callable[[Any, str, Any], Awaitable[None]]
# Async ``(client, tree_id, params)`` upload; returns the handle the upload
# created, or None when the record already exists.
UploadHook = Callable[[Any, str, Any], Awaitable[str | None]]
# ``(entity_data, operation)`` save confirmation, for entities without a
# detail formatter.
ResponseFormatter = Callable[[dict, str], str]
# ``(params)`` predicate on the parsed model: re-save this create as an update.
ResavePredicate = Callable[[Any], bool]


@dataclass(frozen=True)
class WriteBinding:
    """Hand-kept write facts for one entity the generic upsert serves.

    Attributes:
        model: Hand model the arguments are parsed through (extra=forbid).
            Its ``to_api_payload`` hook shapes the request body.
        nudge_citation: Append the "add a source" reminder when a record
            is created without a citation_list.
        reference_checks: Hooks that raise McpToolError when a referenced
            record is missing or the write would lose stored data; all run
            before any write.
        media_upload: Hook run after the checks and before the write. A
            returned handle turns the write into a PUT on that record.
        empty_arguments_error: Message raised (as ValueError, so it gets
            the "<entity> save" context) when no arguments are given, in
            place of the model's own create errors.
        format_response: Builds the confirmation instead of the shared
            save formatter, or None.
        resave_after_create: When it holds for the parsed params, a create
            is followed by a PUT of the same fields on the new handle, so
            Gramps Web runs the bookkeeping it does only on update.
    """

    model: type
    nudge_citation: bool
    reference_checks: tuple[WriteHook, ...] = ()
    media_upload: UploadHook | None = None
    empty_arguments_error: str | None = None
    format_response: ResponseFormatter | None = None
    resave_after_create: ResavePredicate | None = None


WRITE_BINDINGS: dict[str, WriteBinding] = {
    "person": WriteBinding(
        PersonData,
        nudge_citation=True,
        reference_checks=(check_person_refs,),
        resave_after_create=has_event_refs,
    ),
    "family": WriteBinding(FamilySaveParams, nudge_citation=False),
    "event": WriteBinding(EventSaveParams, nudge_citation=True),
    "place": WriteBinding(PlaceSaveParams, nudge_citation=True),
    "source": WriteBinding(SourceSaveParams, nudge_citation=False),
    "citation": WriteBinding(
        CitationData, nudge_citation=False, reference_checks=(check_citation_source,)
    ),
    "note": WriteBinding(
        NoteSaveParams, nudge_citation=False, reference_checks=(check_note_text,)
    ),
    "media": WriteBinding(
        MediaSaveParams,
        nudge_citation=True,
        media_upload=upload_media,
        empty_arguments_error="file_location is required to create new media.",
    ),
    "repository": WriteBinding(RepositoryData, nudge_citation=False),
    # Reason: tags have no list fields, so no list_mode; the client's PUT
    # still keeps stored values for omitted scalars (#97).
    "tag": WriteBinding(
        TagSaveParams, nudge_citation=False, format_response=format_tag_save
    ),
}


def write_row(
    entity: str, table: Mapping[str, EntityResource] = ENTITY_RESOURCES
) -> EntityResource:
    """
    Return the table row for an upsert, checked for POST and PUT.

    Args:
        entity (str): Entity key.
        table (Mapping[str, EntityResource]): Resource rows.

    Returns:
        EntityResource: The row; POST on its collection path creates,
            PUT on its item path updates.

    Raises:
        ValueError: Unknown entity, or POST/PUT missing from the row.
    """
    row = _row(entity, table)
    _check_verb("POST", row.collection_path, entity, row.collection_verbs)
    _check_verb("PUT", row.item_path, entity, row.item_verbs)
    return row


# Operation name -> (entity, summary, description), in listing order.
_UPSERT_TEXT: dict[str, tuple[str, str, str]] = {
    "upsert_person": (
        "person",
        "Create or update a person record",
        "Create or update person information including family links, "
        "event associations, and alternate names (AKA, married names)",
    ),
    "upsert_family": (
        "family",
        "Create or update a family unit",
        "Create or update family unit including member relationships",
    ),
    "upsert_event": (
        "event",
        "Create or update a life event",
        "Create or update life event including person/place associations",
    ),
    "upsert_place": (
        "place",
        "Create or update a geographic location",
        "Create or update geographic location",
    ),
    "upsert_source": (
        "source",
        "Create or update a source document",
        "Create or update source document",
    ),
    "upsert_citation": (
        "citation",
        "Create or update a citation",
        "Create or update citation including object associations",
    ),
    "upsert_note": (
        "note",
        "Create or update a textual note",
        "Create or update textual note including object associations. "
        "To edit text, start from get, not from a search result: an update "
        "built on a shortened read is refused.",
    ),
    "upsert_media": (
        "media",
        "Create or update a media record with optional file upload",
        "Create or update a media record (photo, document, etc.) and its metadata. "
        "When creating (no handle): provide file_location as an absolute local "
        "file path -- the file is uploaded and a new record is created. "
        "When updating (provide handle): omit file_location; only metadata fields "
        "(desc, date, mime, etc.) are changed. "
        "Note: path is the Gramps-relative storage path, not the upload source.",
    ),
    "upsert_repository": (
        "repository",
        "Create or update a repository",
        "Create or update repository information",
    ),
    "upsert_tag": (
        "tag",
        "Create or update a tag",
        "Create a tag with name, color, and priority, or update an existing "
        "one by passing its handle. On update, omitted fields keep their "
        "stored value; tags have no list fields, so list_mode does not apply.",
    ),
}


def upsert_overlays() -> tuple[OpOverlay, ...]:
    """
    Return the overlays for the generic upserts (all ten entities).

    Each one checks its row for POST and PUT, takes its params schema from
    ``WRITE_BINDINGS`` and its handler from the generic upsert module.

    Reason: the handlers are imported here, not at module level, because
    ``tools/upsert_table`` imports the bindings from this module.

    Returns:
        tuple[OpOverlay, ...]: One overlay per generic upsert operation.

    Raises:
        ValueError: A bound entity whose row lacks POST or PUT.
    """
    from .tools.upsert_table import UPSERT_HANDLERS

    overlays = []
    for name, (entity, summary, description) in _UPSERT_TEXT.items():
        write_row(entity)
        overlays.append(
            OpOverlay(
                name=name,
                summary=summary,
                description=description,
                category="write",
                params_schema=WRITE_BINDINGS[entity].model,
                handler=UPSERT_HANDLERS[entity],
                read_only=False,
                destructive=False,
                scope="collection",
                verb="POST",
                entities=(entity,),
            )
        )
    return tuple(overlays)
