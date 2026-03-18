# TODO

## Open

- [ ] **Fix integration test GQL queries** (`test_search_basic.py`): 41 tests fail with
  `make test-integration` after tightened assertions. Audit which GQL filters actually
  match the seed dataset (`tests/fixtures/seed.gramps`) and replace with queries
  guaranteed to return results:
  - `'title ~ "Baptize"'` for sources — verify or replace
  - `'name ~ "Library"'` for repositories — verify or replace
  - `'page ~ "1624"'` for citations — verify or replace
  - `'desc ~ "birth record"'` for media — verify or replace
  Also investigate `test_search_details.py` failures (unrelated to our changes — may
  be a Docker seeding fluke).

- [ ] **test_server.py**: 13 tests marked `@pytest.mark.server` are never run in any
  pipeline. Options: delete them, add a CI job that starts the MCP server, or convert
  to in-process integration tests.

- [ ] **CI skip count assertion**: Add a CI step that fails if more than N integration
  tests are skipped unexpectedly (guard against silent regressions).
