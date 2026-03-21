# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.1] - 2026-03-20

### Fixed
- `upsert_media` now gracefully handles 409 Conflict when replacing a media file with
  identical content (same checksum). The duplicate upload is skipped and the metadata-only
  update proceeds normally. Previously this caused a hard failure.

### Changed
- `summarize_params()` in `operations.py` now surfaces enum member values in type strings,
  so `search` results show `EntityType: person, family, event, ...` instead of just
  `EntityType` — eliminates LLM guesswork about valid values
- `get` operation summary and description now explicitly state "There are no per-type get
  operations" and "Pass params.type to specify the entity kind" with explicit anti-patterns
  (`Do NOT use 'get_person' or 'get_media'`)
- `search` and `delete` operation summaries now include "Do NOT use per-type names"
  warnings (e.g. `search_person`, `delete_event`)
- `SimpleGetParams.type` description corrected from "person or family" to the full list of
  9 valid entity types
- `search` tool description now warns that `query` is a top-level parameter (not inside
  `params`) — fixes shape-copying mistake where LLMs mirror `execute`'s call structure
- `execute` tool description now explicitly states the `operation='get' + params.type='media'`
  pattern (not `'get_media'`)
- All 8 upsert Pydantic models converted from field-level required to `model_validator`
  create-required: fields are now `Optional` (allowing partial updates) with a validator
  that enforces presence only when `handle is None` (create mode). Affected:
  `MediaSaveParams.desc`, `PersonData.primary_name/gender`, `EventSaveParams.type/citation_list`,
  `PlaceSaveParams.place_type`, `SourceSaveParams.title`, `CitationData.source_handle`,
  `NoteSaveParams.text/type`, `RepositoryData.name/type`
- `meta_execute.py`: added prefix-based operation name suggestions after difflib — catches
  per-type names like `get_media` → suggests `get`, `search_person` → suggests `search`
- `test_parameter_alignment.py`: updated 8 alignment tests to reflect create-required
  (model_validator) vs field-level required pattern
- `test_parameter_validators.py`: `test_desc_is_required` updated to `test_desc_is_create_required`

### Added
- `TestUpsertPartialUpdate` in `test_data_management_unit.py`: 10 pure Pydantic tests
  verifying all 8 upsert models accept partial updates (handle present) and reject
  missing required fields on create (handle absent)
- 4 prefix suggestion tests in `test_meta_tools.py`: verify `get_media`, `search_person`,
  `delete_event` all surface the correct generic operation name in the error message
- `test_get_description_mentions_type_parameter` in `test_search_unit.py`
- 2 unit tests for 409 Conflict handling in `test_data_management_unit.py`:
  `test_update_media_409_skips_upload` and `test_update_media_non_409_error_propagates`

## [2.1.0] - 2026-03-20

### Added
- `download_media` operation: download media files from Gramps Web to local disk.
  Accepts handle or gramps_id plus an absolute destination path. Includes path
  security validation (absolute path required, no traversal, parent must exist).
  Category: read, read_only: true. (Closes #30)
- `MediaClient.download_media_file()`: binary download method returning
  `(bytes, content_type)` via `GET /media/{handle}/file`.
- `MediaDownloadParams` Pydantic model with cross-field validator (handle or
  gramps_id required).
- `tests/test_download_media_unit.py`: 9 unit tests for handler validation and
  mocked download flows.
- `TestMediaClientDownload` in `test_client_unit.py`: 3 unit tests for binary
  download request building and error handling.
- `TestDownloadMediaTool` in `test_data_management.py`: 2 integration tests.

### Changed
- Operation count: 19 -> 20 (2 meta-tools, 20 operations).
- Read category: 2 -> 3 operations (`get`, `get_tree_stats`, `download_media`).

## [2.0.0] - 2026-03-19 (Code Mode architecture)

### Breaking
- **19 individual tools replaced by 2 meta-tools**: `search` and `execute`. LLM
  clients now call `search(query="find people")` to discover operations, then
  `execute(operation="search", params={...})` to run them. All 19 operations
  remain available with identical parameters through the `execute` meta-tool.
- **Migration**: `call_tool("upsert_person", {...})` becomes
  `call_tool("execute", {"operation": "upsert_person", "params": {...}})`.
  `call_tool("search", {"query": "person"})` discovers available operations.

### Added
- `src/gramps_mcp/operations.py`: Operation registry (`OPERATION_REGISTRY`) with
  `OperationEntry` dataclass, `search_operations()` keyword search, and
  `summarize_params()` for parameter summaries. Single source of truth for all
  19 operations (MCP-30).
- `src/gramps_mcp/tools/meta_search.py`: `search` meta-tool handler — queries the
  operation registry and returns structured results with parameter schemas.
- `src/gramps_mcp/tools/meta_execute.py`: `execute` meta-tool handler — validates
  operation name, dispatches to the registered handler, and provides close-match
  suggestions for typos.
- `tests/test_operations.py`: 24 unit tests for registry completeness, search
  algorithm scoring, and parameter summarization.
- `tests/test_meta_tools.py`: 15 unit tests for search and execute meta-tool
  handlers, including error handling and dispatch validation.
- Root endpoint now includes `operations_count` alongside `tools_count`.
- Health endpoint now includes `operations` count alongside `tools` count.

### Changed
- Tool count: 19 individual tools reduced to 2 meta-tools (`search` + `execute`).
  Token overhead for tool schemas drops from ~19K to ~1K tokens.
- `server.py`: Registers 2 meta-tools instead of 19 individual tools. Both
  HTTP and stdio transports use the new `_META_TOOLS` dict.
- `search` meta-tool: `readOnlyHint=True, openWorldHint=False` (local registry).
- `execute` meta-tool: `readOnlyHint=False, openWorldHint=True` (external API).

### Removed
- `server_tools.py`: Replaced by `operations.py`. `TOOL_REGISTRY` dict,
  `_READ_ANNOTATIONS`, `_WRITE_ANNOTATIONS`, `_DELETE_ANNOTATIONS` annotation
  presets, and `TreeInfoParams`, `DescendantsParams`, `AncestorsParams` models
  all moved to `operations.py`.

## 2026-03-19 (GQL search discoverability)

### Added
- `tools/_gql_hints.py`: runtime smart hints for common GQL property-path mistakes.
  `gql_hint(entity_type, gql)` returns a corrective message when the query uses bare
  `name`, `surname`, or `firstname`/`first_name` on people (HTTP 200 silent zero-result
  bug — these are not valid Person properties in GQL).
- GQL documentation resource (`gql://documentation`) extended with a "Quick Reference
  by Entity Type" section: copy-paste GQL examples for Person, Family, Event, Place,
  Source, Citation, Note, Media, Repository.
- Search tool description explicitly warns: use `primary_name.first_name` and
  `primary_name.surname_list[0].surname` for person name searches (not bare `name`).

### Changed
- `_search_entities()` in `search_basic.py`: when results are empty, appends
  `Hint: <corrective message>` to the response if a known GQL mistake is detected.
- 13 new unit tests in `test_search_unit.py`: `TestGqlHint` (10 pure-function tests),
  `TestSearchEntitiesGqlHint` (2 integration tests), `TestSearchToolDescription` (1 test).
  `_gql_hints.py` has 100% branch coverage.

## 2026-03-17 (test suite quality)

### Changed
- `test_search_basic.py`: Removed redundant `load_dotenv()` (conftest.py owns env setup);
  tightened assertions from `"Found" or "No X found"` to require `"Found"` — exposes a
  known issue: several GQL queries return no results against the seed dataset (see TODO)
- `test_auth_integration.py`: Removed silent-pass `try/except ValueError` from
  `test_authentication_attempt` and `test_get_token_flow`; auth failure in integration
  context is now a real test failure
- `test_unified_api.py`: Extracted 3 pure URL-building tests (`test_build_url_*`) from
  `@pytest.mark.integration` class into unmarked `TestUrlBuilding` — they now run without Docker
- `test_auth_unit.py`: Added `TestConfigLoading` with 2 tests for settings/init that
  were incorrectly integration-marked; removed redundant singleton test
- `test_data_management.py`: Removed 2 validation-only tests already covered by
  `test_data_management_unit.py::TestUpsertMediaTool`; added ordering comment
- `test_complete_workflow.py`: Deleted dead `_create_or_find_person` legacy method
- `conftest.py`: Added shared `extract_handle(text)` utility function
- `pyproject.toml`: Removed `black>=26.3.1` from `[project.dependencies]` (was
  incorrectly a runtime dep; remains in dev group); removed unused `pytest-rerunfailures`

### Added
- `tests/conftest.py`: `extract_handle(text: str) -> str` shared test utility



### Added
- `.github/dependabot.yml`: monthly Dependabot updates for `pip`, `github-actions`,
  and `docker` ecosystems
- API version validation: server verifies Gramps Web API >= 3.x on first connection
  and raises a clear error for unsupported API 2.x instances
- `GrampsWebAPIClient.bulk_delete()`: validated public method for bulk entity deletion
  via `POST /objects/delete/` — replaces direct `_build_url`/`_make_request` calls in
  `_delete_via_bulk` and `conftest.py`, fixing MCP-18 violation
- `server_lifespan` FastMCP context manager in `server.py` — verifies API version
  before accepting HTTP connections (complements existing stdio startup verification)
- `DeletableEntityType` enum (10 types, including TAG) in `simple_params.py` —
  `DeleteParams.type` now uses this; `EntityType` retains 9 searchable types (no TAG)
  so LLMs cannot call `search(type="tag")` or `get(type="tag")` with invalid intent
- `tests/test_search_unit.py`: unit tests for `search_tool` and `get_tool` error paths
- `TestBulkDelete` in `test_client_unit.py`: 4 tests for `bulk_delete()` validation
- `TestServerLifespan` in `test_api_version.py`: tests lifespan hook wiring

### Changed
- All plain-text error returns in `search_tool`, `get_tool`, `delete_tool` converted to
  `raise McpToolError(...)` (MCP-8 compliance — LLMs now receive `isError=True`)
- `_extract_entity_data()` raises `ValueError("API returned an empty response")`
  instead of returning `None` — prevents silent `AttributeError` at call sites
- `startup.py` import moved to top-level so tests can patch
  `src.gramps_mcp.startup.GrampsWebAPIClient` (standard unittest.mock pattern)
- `conftest.py` no longer imports private symbols `_ENTITY_CLASS_NAMES` or
  `_delete_via_bulk`; uses `client.bulk_delete()` directly

### Changed
- Upgraded test Docker image from `grampsweb:v25.3.0` (Gramps 5.2) to `26.2.0`
  (Gramps 6.0) — fixes seed import failure caused by XML 1.7.2 version mismatch
- **Breaking**: Now requires Gramps Web API 3.x (Gramps Web 26.x or later);
  API 2.x (Gramps Web 25.x) is no longer supported
- Pagination changed from 0-based to 1-based to match API 3.x (`page=1` is now
  the first page)
- Tag deletion now uses bulk `POST /objects/delete/` endpoint (API 3.x removed
  `DELETE /tags/{handle}`)
- Tree stats formatting no longer shows media storage in MB (field removed in
  API 3.x)
- Test artifact sweep updated for 1-based pagination and bulk tag deletion

### Removed
- Diagnostic "Gramps plugin state" CI step (no longer needed)
- Tag update support (`upsert_tag` with handle) — tags are immutable after
  creation in API 3.x

## 2026-03-15 (test coverage)

### Added
- Five new unit test files bringing branch coverage from ~62% to **89.33%** — the
  80% threshold is now met by unit tests alone without Docker:
  - `tests/test_client_unit.py`: 34 tests for `client.py` pure functions, URL
    building, `_make_request` retry/error/header branches, `make_api_call` routing
  - `tests/test_auth_unit.py`: 18 tests for `AuthManager` singleton, token
    lifecycle, `authenticate`/`get_token`/`get_headers`/`close`
  - `tests/test_data_management_unit.py`: 26 tests for CRUD helpers
    (`_extract_entity_data`, `_format_save_response`, `_handle_crud_operation`,
    `delete_tool`, `upsert_family/repository/tag/media_tool`)
  - `tests/test_analysis_unit.py`: 33 tests for task polling, report tools
    (`get_descendants_tool`, `get_ancestors_tool`, `get_recent_changes_tool`,
    `get_tree_stats_tool`), and formatting helpers
  - `tests/test_api_mapping_unit.py`: 7 tests for `api_mapping.py` dispatch table

### Changed
- `tests/test_handlers.py`: Added ~44 tests covering previously-untested branches
  in `person_handler`, `family_handler`, `event_handler`,
  `person_detail_handler`, `family_detail_handler`
- `pyproject.toml`: Added `[tool.coverage.run] omit` for 7 unused parameter model
  files that inflated the denominator without contributing covered lines
- Cleaned lint issues across all new and modified test files (`test_client_unit.py`,
  `test_auth_unit.py`, `test_search_unit.py` — unused imports, import sorting, E501)

## 2026-03-15

### Changed

- **Test infrastructure**: Replaced `demo.grampsweb.org` with an ephemeral local Gramps
  Web Docker instance for all integration tests — eliminates network flakiness, shared
  state, rate limits, and external service dependency
- `docker-compose.test.yml`: New compose file with pinned `grampsweb:v25.3.0` + Redis +
  Celery; binds to `127.0.0.1:5055`; shares 5 named volumes between web and celery
- `scripts/seed_test_db.py`: New standalone seed script — polls health endpoint, creates
  owner user via `docker compose exec`, authenticates, imports `seed.gramps` via raw
  binary body (`application/octet-stream`), polls async task, rebuilds search index,
  verifies `I0001` exists
- `tests/fixtures/seed.gramps`: Vendored example.gramps dataset (2,157 people, 762
  families) — no runtime download required
- `Makefile`: Added `test-unit` (no Docker, 60% coverage floor), `test-integration`
  (full Docker lifecycle: teardown → up → seed → pytest → teardown), `docker-up/down/seed`
- `tests/conftest.py`: Default URL changed to `http://localhost:5055`; added
  `pytest_collection_modifyitems` hook — skips `@pytest.mark.integration` tests locally
  when Docker is unreachable; fails (not skips) when `REQUIRE_INTEGRATION=1`
- `tests/`: Added `pytestmark = pytest.mark.integration` to 8 test files; used
  class-level marker on `TestUnifiedApiCall` to preserve unit tests in same file
- `.github/workflows/ci.yml`: Test job now starts Docker, seeds data, runs tests, tears
  down; `COMPOSE_PROJECT_NAME` per matrix Python version; Docker image caching via
  `actions/cache`; `REQUIRE_INTEGRATION=1` ensures no silent skips in CI

### Fixed

- Removed 5 demo-server-specific `xfail`/`skip` workarounds: `test_find_anything`,
  `test_get_descendants_real_api`, `test_replace_note_list_on_event`,
  `test_create_tag_success`, `test_place_hierarchy_creation` — none apply to a fresh
  ephemeral instance
- Updated search queries to match example.gramps data: source `"census"` → `"Baptize"`,
  repository `"archive"` → `"Library"`, media `"pietrala"` → `"birth record"`, full-text
  `"pietrala"` → `"Warner"`

## [1.1.1] - 2026-03-13

### Fixed
- `upsert_media`: `file_location` parameter added to `MediaSaveParams` so it appears in
  the MCP schema and is discoverable by LLM clients — previously invisible, causing
  "file_location is required to create new media" errors when clients used `description`
  or `path` as the upload source
- `upsert_media`: Remove duplicate `description` field from `MediaSaveParams`; use `desc`
  (the Gramps-native field) consistently
- `delete_tool`: Replace manual `arguments.get()` extraction with `DeleteParams` Pydantic
  validation; remove defensive enum normalization that Pydantic already handles
- `upsert_repository_tool`: Remove pre-Pydantic manual checks that returned bare
  `TextContent` errors; validation errors now route through `raise_tool_error` consistently

### Tests
- Add `TestMediaSaveParams` unit tests (no network) for schema shape
- Add `TestCreateMediaToolValidation` integration tests: missing `file_location`, bad path,
  update without `file_location`

## 2026-03-13

### Changed

- `Dockerfile` converted to multi-stage build: `ghcr.io/astral-sh/uv:python3.11-bookworm-slim` builder + `python:3.11-slim-bookworm` runtime; build artefacts (`curl`, `ca-certificates`, `uv`) no longer present in the runtime layer
- `HEALTHCHECK` replaced `curl -f http://localhost:8000/health` with a Python `urllib.request` one-liner — eliminates curl from the runtime image
- `mypy` replaced by `pyright` (standard mode) as the type checker; `mypy` removed from dev dependencies, `pyright>=1.1.0` added; `[tool.pyright]` section added to `pyproject.toml`
- `typecheck` Makefile target now runs `uv run pyright src/`; CI lint job updated to match
- `mirrors-mypy` pre-commit hook removed (no official pyright pre-commit mirror; type-checking is CI+Makefile only)
- `requires-python` lowered from `>=3.11` to `>=3.10`; CI test matrix extended to `["3.10", "3.11", "3.12", "3.13"]`
- Fixed 9 latent "possibly unbound" bugs in `search_details.py` and 2 in `analysis.py` — handle/gramps_id extraction moved before `try` blocks so error-handler clauses always have a bound variable
- Added `-> Any:` return type to `client._make_request` and `data_management._extract_entity_data` to satisfy pyright's union inference (runtime behaviour unchanged)
- `auth.py`: `data["access_token"]` now explicitly cast to `str`; added `assert is not None` guard before return

## 2026-03-12 (AGPL Copyright Headers + CI Enforcement)

### Added
- AGPL-3.0 copyright headers on all 53 Python files in `src/` and `scripts/`, using three templates: A (original code only, 20 files), B (both authors for modified files, 32 files), C (fork author only for new files, 1 file — `tools/_errors.py`)
- `scripts/check_copyright_header.py`: pre-commit hook that verifies the project identifier line and AGPL license reference appear within the first 20 lines of every `src/` and `scripts/` Python file
- Pre-commit hook `check-copyright-header` in `.pre-commit-config.yaml`, scoped to `^(src|scripts)/.*\.py$`
- "Check copyright headers" step in the CI `lint` job in `.github/workflows/ci.yml`
- README.md License section rewritten to identify this project as a fork of [cabout.me/gramps-mcp](https://github.com/caboutme/gramps-mcp) with gratitude for open-sourcing; Acknowledgments section updated with cabout.me as first entry

## 2026-03-12 (Fail-Loud Config + Test Infrastructure)

### Changed
- `get_settings()` in `config.py` now raises `ValueError` listing all missing required env vars (`GRAMPS_API_URL`, `GRAMPS_USERNAME`, `GRAMPS_PASSWORD`) instead of silently falling back to demo credentials — prevents users unknowingly connecting to `demo.grampsweb.org`
- `tests/conftest.py` sets demo env vars via `os.environ.setdefault()` in a `pytest_configure()` hook (fires before collection/imports so `lru_cache` is never polluted); prints a targeting banner showing which server tests will run against

### Added
- `TestSettingsValidation.test_missing_env_vars_raises` in `test_tool_annotations.py`: asserts fail-loud behavior without network
- CI Test step now has explicit `env:` block with demo credentials for visibility

### Removed
- `test-sweep` Makefile target: redundant since artifact cleanup is automatic via 4-layer chain (pre-test sweep → fixture teardown → `pytest_sessionfinish` → atexit)

## 2026-03-11 (Resilient Recent Changes)

### Fixed
- `test_get_recent_changes_real_api` no longer fails when all recent transactions are deletions — assertion now accepts either gramps IDs (e.g., `I0001`) or `(deleted)` annotation
- `_format_recent_changes` in `analysis.py` shows deleted objects as `abc123456789... (deleted)` instead of raw hex handles
- Numeric `obj_class` codes (e.g., `5`) in transaction history are now resolved to names (`Place`) before display

### Added
- `normalize_obj_class()` in `utils.py`: converts Gramps internal numeric class codes (0–9) to canonical string names; passes string names through unchanged
- `_CLASS_TO_API_CALL` dispatch dict in `utils.py` replaces the 9-branch `if/elif` chain in `get_gramps_id_from_handle`
- 8 unit tests for `normalize_obj_class` in `tests/test_utils.py::TestNormalizeObjClass`
- 5 unit tests for `_format_recent_changes` in `tests/test_handlers.py::TestFormatRecentChanges`

## 2026-03-11 (Harden Test Artifact Sweep)

### Fixed
- `sweep_test_artifacts()` now finds and removes orphaned events and citations — added `event` (filter: `description ~ "MCP_TEST_"`) and `citation` (filter: `page ~ "MCP_TEST_"`) to `_SWEEP_GQL_FILTERS` in `tests/conftest.py`
- Families (which have no text field) are now swept via a person→family cascade: after finding test persons via GQL, their `family_list` handles are added to the delete queue
- All event creation calls in `tests/test_data_management.py` now include a `description` field with the `MCP_TEST_` prefix, making them discoverable by the sweep
- All citation creation calls in `tests/test_data_management.py` now include the `MCP_TEST_` prefix in the `page` field

### Added
- `_paginated_gql_query()` helper in `tests/conftest.py`: loops through pages until exhausted, ensuring the sweep catches all orphans even when artifact count exceeds a single page

## 2026-03-11 (Sweep Notes Fallback)

### Fixed
- `sweep_test_artifacts()` no longer emits a server-error warning for notes.
  The Gramps Web demo server's GQL engine returns 500 for any note query.
  Removed `note` from `_SWEEP_GQL_FILTERS`; added `_sweep_notes_fallback()`
  which lists all notes via `GET /notes/?pagesize=200` and filters client-side
  for the `MCP_TEST_` prefix, handling the `StyledText` dict wrapper.

## 2026-03-11 (Cleanup Infrastructure)

### Added
- `pytest_sessionfinish` hook in `tests/conftest.py`: sweeps `MCP_TEST_` artifacts after every pytest run, unconditionally — even when only unit tests ran or fixture teardown missed some entities. Acts as the final safety net in the 4-layer cleanup chain (pre-test sweep → registry teardown → session finish → atexit).

### Fixed
- Import ordering lint violation (`I001`) in `tests/conftest.py`: moved `import pytest` before local imports to satisfy ruff isort rules.

## 2026-03-11 (Sprint A — MCP Best Practices)

### Added
- 28 MCP Server Design rules (MCP-1 through MCP-28) added to CLAUDE.md covering: tool naming, descriptions, error handling, resources, transport/logging, security, performance, and testing
- `tools/_errors.py`: single source of truth for tool error handling — `McpToolError` exception and `raise_tool_error(-> NoReturn)` helper (MCP-8, MCP-10)

### Fixed
- Tool errors now propagate as exceptions so the MCP SDK sets `isError=True` on responses, allowing the LLM to distinguish errors from valid data (MCP-8)
- `load_resource()` now raises `FileNotFoundError`/`OSError` instead of returning error strings (MCP-13)
- `logging.basicConfig` explicitly sets `stream=sys.stderr` — required for stdio transport (MCP-15)
- HTTP server default host changed from `0.0.0.0` to `127.0.0.1`; configurable via `GRAMPS_MCP_HOST`/`GRAMPS_MCP_PORT` env vars (MCP-20)
- ~25 bare `except Exception: continue/pass` blocks across 13 handler files upgraded to log at `warning` level (MCP-11)
- Hardcoded tool count `19` removed; all references now use `len(TOOL_REGISTRY)` (MCP-6)
- Version synced: `src/gramps_mcp/__init__.py` bumped from `0.1.0` to `1.1.0` to match `pyproject.toml`
- Deleted dead `tools.py` re-export shim
- Error-case tests updated to use `pytest.raises(McpToolError)` instead of asserting on return text

## 2026-03-11 (Feature Gaps Sprint)

### Added

- `get_type` tool now supports all 9 entity types: event, place, source, citation, note, media, repository (was person/family only) — added 7 `@with_client` handler functions and `_GET_TOOL_DISPATCH` dispatch dict in `search_details.py`
- `delete_type` tool: deletes any of the 9 entity types by handle; uses `DELETE_API_CALLS` dispatch dict mapping type → API endpoint; added `DeleteParams` model
- `create_tag` tool: creates or updates tags (name, color, priority) via POST/PUT `tags/` endpoint
- `find_tags` tool: lists all tags in the tree as a formatted markdown list with handle and color
- `list_mode` parameter on all create/update tools: `"merge"` (default, existing behavior) or `"replace"` to overwrite list fields instead of appending; field is popped from payload before Gramps API call so it stays transparent to the upstream API
- stdio transport now serves `gql://documentation` and `gramps://usage-guide` resources via `list_resources`/`read_resource` handlers (previously HTTP-only via FastMCP decorators)
- Integration tests for all new features: `TestListModeReplace`, `TestDeleteTypeTool`, `TestCreateTagTool`, 7 new `get_type` tests for each newly-supported entity type

### Changed

- Tool count: 16 → 19 (`delete_type`, `create_tag`, `find_tags`)
- `GetEntityType` enum extended from 2 to 9 values (all entity types)
- CLAUDE.md: updated MCP coverage table, removed architectural limitation note for `list_mode`

## 2026-03-11

### Added

- Complete Gramps Web API reference in CLAUDE.md: all endpoints (entity CRUD, analysis, reports/export, utility), query parameters (extend, profile, sort, gql, dates), full data models with JSON examples for all 10 entity types and sub-objects (Date, EventReference, ChildReference, MediaReference, PlaceReference, etc.), GQL quick-reference, and current MCP coverage gap analysis

### Fixed

- Corrected 10 mypy type errors across 5 files: `str | None` param and return types in `event_handler.py` and `data_management.py`, `BaseModel | None` return in `api_mapping.py`, `float` annotation for `sleep_interval` in `analysis.py`, and None guard in `find_type_tool`
- Fixed Python 3.10 f-string backslash incompatibility in `tests/test_analysis.py` (4 occurrences) by extracting `split('\n')` calls to variables
- Auto-formatted 15 files with `ruff format` (trailing commas, whitespace)

### Added

- CI pipeline with linting, type checking, and multi-version test matrix
- Test coverage measurement with pytest-cov (branch coverage)
- Dependency security scanning with pip-audit in CI
- mypy pre-commit hook for local type checking
- Makefile with standard targets (install, lint, test, audit, clean, ci)
- Copyright and license notices to all source files

### Changed

- Migrated pytest config from pytest.ini to pyproject.toml
- Config initially fell back to demo instance defaults when env vars are unset (superseded by fail-loud behavior in 2026-03-12)

## [1.1.0]

### Added

- GitHub Container Registry (GHCR) publishing support (#12)

### Fixed

- Person event reference update merging (#10, #9)
- Overly permissive regex ranges in emoji detection (#3)
- Incomplete URL substring sanitization (#2)
- GitHub Actions Docker build failures (#13)

### Changed

- Optimized Docker builds for development and release (#14)
- Updated OpenWebUI instructions to use mcpo proxy approach (#18)

## [1.0.0]

### Added

- 16 MCP tools for genealogy research and management
- Smart search with Gramps Query Language (GQL)
- Full-text search across all record types
- Create/update operations for all entity types
- Tree analysis (descendants, ancestors, recent changes)
- JWT authentication with automatic token refresh
- Docker and standalone deployment options
- MCP resources: GQL documentation, usage guide
- Support for Claude Desktop, OpenWebUI, Claude Code
- Pre-commit hooks (ruff, file length, copyright, emoji check)
- Comprehensive integration test suite
