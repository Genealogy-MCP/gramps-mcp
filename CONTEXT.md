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
