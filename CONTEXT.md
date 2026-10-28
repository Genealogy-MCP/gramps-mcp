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
  the gramps-webapi version it describes (3.24.0, what the Docker test image
  runs). Codegen reads it; CI never fetches the spec live.
- **overlay**: a handwritten, per-entity hook bound to a resource-table row
  that carries behaviour the spec cannot express: payload rewrites
  (StyledText wrap, `child_handles` to `child_ref_list`), pre-write reference
  checks, post-create steps (media file upload), read-side joins (timeline).
- **drift**: any mismatch between snapshot, table, write models, or the live
  server. Snapshot-vs-table fails CI; hand-model field missing from the spec
  fails a unit test; spec field missing from a model is a warning; live
  server version differing from the snapshot logs a startup warning.
