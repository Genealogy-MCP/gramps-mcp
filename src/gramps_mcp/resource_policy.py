# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Handwritten policy the schema snapshot cannot express.

The gramps-webapi OpenAPI document declares no request-body schemas on POST
and PUT and marks nothing `readOnly`, so codegen needs three maps from a
human: which component describes each entity, which component fields the
server computes, and the Person field list taken from upstream
`PersonSchema` at the pinned version. Later slices add the per-entity
overlays here.
"""

# Entity name (as the `type` parameter of get/search/delete spells it) to the
# `components.schemas` entry that describes its record.
ENTITY_COMPONENTS = {
    "person": "Person",
    "family": "Family",
    "event": "Event",
    "place": "Place",
    "citation": "Citation",
    "source": "Source",
    "repository": "Repository",
    "media": "Media",
    "note": "Note",
    "tag": "Tag",
}

# Entity name to its collection path, relative to the API root. The spec
# keys paths by URL, so the collection each entity lives at is policy too.
ENTITY_COLLECTIONS = {
    "person": "people/",
    "family": "families/",
    "event": "events/",
    "place": "places/",
    "citation": "citations/",
    "source": "sources/",
    "repository": "repositories/",
    "media": "media/",
    "note": "notes/",
    "tag": "tags/",
}

# Fields every component may list that the server computes or that only
# appear on reads (`?backlinks=1`, `?profile=...`, `?extend=...`). They are
# never writable, so codegen drops them from every row.
READ_ONLY_FIELDS = (
    "_class",
    "handle",
    "change",
    "backlinks",
    "profile",
    "extended",
    "birth_ref_index",
    "death_ref_index",
    # Media: computed from the uploaded file bytes on the server.
    "checksum",
)

# Fields of `PersonSchema` in gramps_webapi/api/resources/schemas.py at the
# pinned tag (the sidecar records the URL). Codegen uses this list when the
# snapshot registers no Person component, and fails when the component it
# does register disagrees with it, so an upstream change to PersonSchema is
# caught at the next `make schema-fetch` rather than hidden.
PERSON_SCHEMA_FIELDS = (
    "_class",
    "address_list",
    "alternate_names",
    "attribute_list",
    "backlinks",
    "birth_ref_index",
    "change",
    "citation_list",
    "death_ref_index",
    "event_ref_list",
    "extended",
    "family_list",
    "gender",
    "gramps_id",
    "handle",
    "lds_ord_list",
    "media_list",
    "note_list",
    "parent_family_list",
    "person_ref_list",
    "primary_name",
    "private",
    "profile",
    "tag_list",
    "urls",
)
