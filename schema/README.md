# Schema snapshot

`openapi.json` is the OpenAPI 3.0 document that gramps-web-api serves at
`/api/openapi.json`, captured from the Docker test image pinned in
`docker-compose.test.yml`. `openapi.meta.json` records where it came from:
source URL, image digest, gramps-webapi and Gramps versions, SHA-256,
fetch date, and the upstream `PersonSchema` the Person field list follows.

Refresh with `make schema-fetch`. It refuses a server whose gramps-webapi
version differs from `src/gramps_mcp/schema_pin.py`; bump the pin and pass
`--allow-version-mismatch` to move to a new release, then commit the
snapshot, the sidecar and the regenerated `src/gramps_mcp/resource_table.py`
together. `python -m src.gramps_mcp.codegen --check` runs as a unit test and
fails on any drift between the snapshot and the table.

The document is produced by
[gramps-web-api](https://github.com/gramps-project/gramps-web-api),
copyright the Gramps Web API contributors, and is redistributed here under
the AGPL-3.0, the same licence as this repository.
