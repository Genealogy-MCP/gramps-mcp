# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `.github/dependabot.yml`: monthly Dependabot updates for `pip`, `github-actions`,
  and `docker` ecosystems

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
