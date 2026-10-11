# Glossary

- **merge mode** (`list_mode="merge"`): on upsert, `*_list` fields are
  appended-with-dedup against the stored entity rather than replaced. The
  alternative, `list_mode="replace"`, overwrites the list entirely.
- **reference-object list**: a `*_list` field whose elements are dicts carrying a
  `ref` handle plus qualifiers (e.g. `media_list`, `child_ref_list`,
  `event_ref_list`), as opposed to plain string-handle lists (`note_list`,
  `citation_list`, `tag_list`).
- **discriminator**: the qualifier fields that, together with `ref`, establish a
  reference-object's identity for dedup (e.g. `rect` for media, `frel`/`mrel` for
  child refs, `role` for event refs).
- **association** (`person_ref_list`): a directed, non-parent/child/spouse link
  from one person to another (e.g. cousin, godparent, friend). Each entry is a
  reference-object carrying the associated person's `ref` handle and a free-text
  `rel` descriptor. One-way only — no reciprocal entry is auto-created.
- **resource table**: the generated, checked-in data describing each Gramps
  entity (path, verbs, list filters, writable field names) that the generic
  CRUD handlers read. Produced by the codegen script from the schema snapshot;
  never edited by hand.
- **schema snapshot**: the pinned copy of the Gramps Web OpenAPI document
  (`schema/openapi.json`, fetched from `/api/openapi.json` on the Docker test
  instance by `make schema-fetch`) checked into the repo with a sidecar naming
  the gramps-webapi version it describes (3.16.0, what the Docker test image
  runs). Codegen reads it; CI never fetches the spec live.
- **overlay**: a handwritten, named per-entity binding to a resource-table row
  that carries what the spec cannot express, all kept in
  `src/gramps_mcp/overlays.py`. Read side: routes (`READ_OVERLAYS`: list
  params class, display label, formatter) and the operation overlays for
  `search`, `list_tags`, `get` and `delete`. Write side: `WRITE_BINDINGS`
  (hand model whose payload hook does the rewrites such as the StyledText
  wrap, citation nudge, pre-write reference-check slot, post-write
  media-upload slot) for the upserts the generic handler serves, plus the
  drift allowlist `PAYLOAD_ONLY_FIELDS`. Read-side joins (timeline) and the
  handwritten upserts (person, family, citation, repository, tag, media) stay
  in `tools/`.
- **drift**: any mismatch between snapshot, table, write models, or the live
  server. Snapshot-vs-table fails CI; hand-model field missing from the spec
  fails a unit test; spec field missing from a model is a warning; live
  server version differing from the snapshot logs a startup warning.
