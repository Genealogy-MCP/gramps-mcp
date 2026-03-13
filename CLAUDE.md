### Project Awareness & Context
- **Always read `README.md`** at the start of a new conversation to understand the project's setup, features, and usage.
- **Use consistent naming conventions, file structure, and architecture patterns** following Python and MCP best practices.
- **Use uv** for all Python dependency management and command execution.
  - **Commands**: Use `uv run python` or `uv run <command>` for executing Python scripts and tests
  - **Dependencies**: Use `uv add <package>` to add dependencies, `uv sync` to install
  - **Git commits**: Use `uv run git commit` to ensure pre-commit hooks run correctly

### Code Structure & Modularity
- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
  For this MCP server project:
    - `server.py` - Main MCP server setup and routing
    - `tools/` directory - MCP tool implementations organized by feature
    - `client.py` - Gramps Web API client
    - `auth.py` - JWT authentication handling
    - `models/` directory - Pydantic models for validation
    - `config.py` - Configuration management
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use python_dotenv and load_dotenv()** for environment variables.

### Testing & Reliability (TDD Approach)
- **This project follows Test-Driven Development (TDD) practices**.
- **Write tests FIRST before implementing functionality** - red, green, refactor cycle.
- **Always create Pytest integration tests for new features** (functions, classes, routes, etc).
- **Use real APIs for testing - no mocks, fixtures, or test clients**.
- **After updating any logic**, check whether existing tests need to be updated. If so, do it.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
- **Run tests frequently during development** using `uv run pytest` or `uv run pytest -xvs` for verbose output.


### Style & Conventions
- **Use Python** as the primary language.
- **Follow PEP8**, use type hints, format with `ruff format`, and lint with `ruff check`.
- **Use `pydantic` for data validation**.
- Use `httpx` for async HTTP client (no FastAPI needed for MCP servers).
- Use `MCP Python SDK` for MCP server implementation.
- Write **docstrings for every function** using the Google style:
  ```python
  def example():
      """
      Brief summary.

      Args:
          param1 (type): Description.

      Returns:
          type: Description.
      """
  ```

### Documentation & Explainability
- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Comment non-obvious code** and ensure everything is understandable to a mid-level developer.
- When writing complex logic, **add an inline `# Reason:` comment** explaining the why, not just the what.

### Known Architectural Limitations
- **List fields support merge or replace on PUT**: Pass `list_mode: "replace"` on any upsert tool to overwrite `*_list` fields instead of merging. Default is `"merge"` (append with dedup). To remove a single item, use `list_mode: "replace"` with the desired final list.
- **No `detach_reference` tool**: To remove a single item from a list field, use `list_mode: "replace"` with the filtered list (GET→filter→PUT with replace).

### MCP Server Design

Rules for building and maintaining this MCP server. Uses RFC 2119 conventions (MUST, SHOULD, etc.).

#### Tool Design

- **MCP-1 (MUST)** Tool names use `snake_case`, 1-64 chars, and are treated as stable identifiers. Renaming a tool is a breaking change.
- **MCP-2 (MUST)** Every tool description explains *what* it does, *when* to use it, *what* it returns, and any caveats. Treat descriptions as onboarding material for an LLM that has never seen this API. Do not describe parameter mechanics (the schema handles that).
- **MCP-3 (SHOULD)** Warn about token-heavy operations in tool descriptions. Include default and maximum limits so the LLM can request less data.
- **MCP-4 (MUST)** Every parameter in `inputSchema` has a `description` field. Use unambiguous names (`person_handle` not `handle` when multiple types accept handles). Include allowed values, constraints, and defaults.
- **MCP-5 (SHOULD)** Provide tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) on every tool. Read-only tools: `readOnlyHint=True`. Destructive tools (delete): `destructiveHint=True`. All tools: `openWorldHint=True` (external API).
- **MCP-6 (MUST)** Derive tool count and tool names from `TOOL_REGISTRY` at runtime. Never hardcode tool counts in health checks, docstrings, or endpoints.
- **MCP-7 (SHOULD)** Add a `response_format` parameter (`"concise"` / `"detailed"`) to search and detail tools so the LLM can control token consumption.

#### Error Handling

- **MCP-8 (MUST)** Tool execution errors are returned as MCP result content with `isError=True`, never as protocol-level errors. The LLM needs to see the error to self-correct.
- **MCP-9 (MUST)** Error messages are specific and actionable: state what went wrong, what was expected, and suggest the corrective action. `"Person with handle 'abc123' not found. Use search to search first."` > `"Record not found."`.
- **MCP-10 (MUST)** Define `_format_error_response` in exactly one shared module (`tools/_errors.py`) and import everywhere. No duplicated error utilities.
- **MCP-11 (MUST NOT)** Silently swallow exceptions with bare `except Exception: continue/pass`. Every caught exception logs at `warning` level minimum with details. Prefer propagating errors so the tool reports them to the LLM.

#### Resources and Prompts

- **MCP-12 (MUST)** Resources use RFC 3986 URIs with `name`, `description`, and `mimeType`. Descriptions explain when and why an LLM should read the resource.
- **MCP-13 (MUST)** `load_resource` raises exceptions on failure (e.g., `FileNotFoundError`), not error strings. Returning an error string is indistinguishable from valid content.
- **MCP-14 (SHOULD)** Define MCP prompts for common multi-step workflows (e.g., source documentation, person research) that encode proper tool-call sequences.

#### Transport and Logging

- **MCP-15 (MUST)** Stdio transport: NEVER write to stdout -- it is the MCP transport channel. Configure all loggers with `stream=sys.stderr`.
- **MCP-16 (SHOULD)** Use FastMCP `Context` for in-tool logging and progress reporting instead of module-level loggers. `Context` routes logs correctly per transport and enables progress notifications.
- **MCP-17 (SHOULD)** In production, enable `mask_error_details=True` so only intentional `ToolError` messages reach clients.

#### Security

- **MCP-18 (MUST)** Validate all tool inputs via Pydantic before making API calls. Never pass raw `arguments` dict fields into URL construction without schema validation.
- **MCP-19 (MUST)** Never expose internal handles, file paths, stack traces, or credentials in tool responses.
- **MCP-20 (MUST)** HTTP transport binds to `127.0.0.1` by default. `0.0.0.0` only in Docker/production with explicit env var (`GRAMPS_MCP_HOST`).

#### Performance

- **MCP-21 (MUST)** Share a single `httpx.AsyncClient` across tool calls within a session (via FastMCP lifespan or module singleton). No client-per-call.
- **MCP-22 (MUST NOT)** Make N+1 API calls in handlers. Use `?extend=all` on parent entities or batch-fetch instead of fetching each child individually.
- **MCP-23 (SHOULD)** Cache `get_settings()` as a module singleton. Settings are immutable during a server session.
- **MCP-24 (SHOULD)** Enforce a `max_results` ceiling on all list/search tools. Return truncation metadata so the LLM can paginate.

#### Testing

- **MCP-25 (MUST)** Unit-test tool parameter validation, error formatting, and output shaping independently from the API. No network required.
- **MCP-26 (MUST)** Integration-test every registered tool: happy path, auth failure, not-found, and invalid-input cases.
- **MCP-27 (SHOULD)** Test stdio transport end-to-end by spawning the server as a subprocess. Verify no non-JSON output leaks to stdout.
- **MCP-28 (SHOULD)** Maintain a tool-quality eval suite: natural-language prompts mapped to expected tool calls. Detect description regressions.

### AI Behavior Rules
- **Never assume missing context. Ask questions if uncertain.**
- **Never hallucinate libraries or functions** – only use known, verified Python packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed to
- **Do not use emojis in the code** to maintain a clean and professional coding style.
- **NEVER use the live Gramps instance for testing.** The MCP-connected Gramps tree contains real family data. All tests must use mocks, a dedicated test instance, or be run against the demo API (demo.grampsweb.org). Creating test records (e.g. "John Smith", "Test Source") in the production tree is a data integrity violation that requires manual cleanup.
- **MCP testing may ONLY use read-only tools.** When verifying MCP server functionality against the live instance, only use read-only tools (`search`, `search_text`, `get`, `get_tree_stats`, `get_ancestors`, `get_descendants`, `get_recent_changes`). NEVER call `upsert_*` tools for testing purposes — those are for real genealogy data entry only, following the user's Change Review Protocol.

---

### Gramps Web API Reference

This section documents the complete Gramps Web API as consumed by the MCP server. All paths are relative to `{GRAMPS_API_URL}/api/`. Authentication uses JWT Bearer tokens obtained via `POST /api/token/`.

#### Authentication

| Endpoint | Method | Description |
|---|---|---|
| `token/` | POST | Obtain JWT access token (body: `{"username": "...", "password": "..."}`) |
| `token/refresh/` | POST | Refresh an existing token |
| `token/create_owner/` | POST | Create initial owner account |

All subsequent requests require header: `Authorization: Bearer <token>`.
The `tree_id` is embedded in the JWT claims and does not appear in URL paths (except `/trees/` endpoints).

---

#### Entity CRUD Endpoints

All 11 entity types follow the same CRUD pattern. Handles are opaque strings (typically 26+ chars) used as unique identifiers.

| Entity | List (GET) | Create (POST) | Get (GET) | Update (PUT) | Delete (DELETE) |
|---|---|---|---|---|---|
| **People** | `people/` | `people/` | `people/{handle}` | `people/{handle}` | `people/{handle}` |
| **Families** | `families/` | `families/` | `families/{handle}` | `families/{handle}` | `families/{handle}` |
| **Events** | `events/` | `events/` | `events/{handle}` | `events/{handle}` | `events/{handle}` |
| **Places** | `places/` | `places/` | `places/{handle}` | `places/{handle}` | `places/{handle}` |
| **Citations** | `citations/` | `citations/` | `citations/{handle}` | `citations/{handle}` | `citations/{handle}` |
| **Sources** | `sources/` | `sources/` | `sources/{handle}` | `sources/{handle}` | `sources/{handle}` |
| **Repositories** | `repositories/` | `repositories/` | `repositories/{handle}` | `repositories/{handle}` | `repositories/{handle}` |
| **Media** | `media/` | `media/` | `media/{handle}` | `media/{handle}` | `media/{handle}` |
| **Notes** | `notes/` | `notes/` | `notes/{handle}` | `notes/{handle}` | `notes/{handle}` |
| **Tags** | `tags/` | `tags/` | `tags/{handle}` | `tags/{handle}` | `tags/{handle}` |

Additional entity-specific endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `people/{handle}/timeline` | GET | Person's life timeline with events |
| `people/{handle}/dna/matches` | GET | DNA matches for a person |
| `people/{handle}/ydna` | GET | Y-DNA data for a person |
| `families/{handle}/timeline` | GET | Timeline for all people in a family |
| `events/{handle1}/span/{handle2}` | GET | Elapsed time span between two events |
| `media/{handle}/file` | GET/PUT | Download or upload the actual media file |
| `media/{handle}/thumbnail/{size}` | GET | Get thumbnail at specified size |
| `media/{handle}/cropped/{x1}/{y1}/{x2}/{y2}` | GET | Get cropped region of media |
| `media/{handle}/face_detection` | GET | Run face detection on media |
| `media/{handle}/ocr` | GET | Run OCR on media |
| `media/archive/` | GET | Export media archive |
| `media/archive/upload/zip` | POST | Import media from ZIP |

Bulk operations:

| Endpoint | Method | Description |
|---|---|---|
| `objects/` | POST | Create multiple objects of any type in one request |
| `objects/delete/` | POST | Delete multiple objects in one request |

---

#### Analysis Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `relations/{handle1}/{handle2}` | GET | Most direct relationship between two people |
| `relations/{handle1}/{handle2}/all` | GET | All possible relationships between two people |
| `living/{handle}` | GET | Whether a person is likely still living |
| `living/{handle}/dates` | GET | Estimated birth/death dates for a person |
| `timelines/people/` | GET | Aggregated timeline for multiple people |
| `timelines/families/` | GET | Aggregated timeline for multiple families |
| `facts/` | GET | Interesting statistical facts about the tree |
| `search/` | GET | Full-text or semantic search across all records |
| `search/index/` | POST | Rebuild the search index |

---

#### Report & Export Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `reports/` | GET | List available report types |
| `reports/{report_id}` | GET | Get info about a specific report |
| `reports/{report_id}/file` | GET/POST | Get/generate a report file |
| `reports/{report_id}/file/processed/{filename}` | GET | Get processed report output |
| `exporters/` | GET | List available export formats |
| `exporters/{extension}` | GET | Get info about a specific exporter |
| `exporters/{extension}/file` | POST | Generate an export file |
| `exporters/{extension}/file/processed/{filename}` | GET | Get processed export output |
| `importers/` | GET | List available import formats |
| `importers/{extension}` | GET | Get info about a specific importer |
| `importers/{extension}/file` | POST | Import a file |

Reports and exports that take time return a task ID for polling via `tasks/{task_id}/`.

---

#### Utility Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `trees/` | GET | List all available trees |
| `trees/{tree_id}` | GET | Get tree info and statistics |
| `trees/{tree_id}/disable` | POST | Disable a tree |
| `trees/{tree_id}/enable` | POST | Enable a tree |
| `trees/{tree_id}/repair` | POST | Check and repair tree integrity |
| `trees/{tree_id}/migrate` | POST | Upgrade tree schema version |
| `tasks/{task_id}` | GET | Poll async task status |
| `transactions/` | POST | Execute a batch transaction |
| `transactions/history/` | GET | Get transaction history |
| `transactions/history/{id}` | GET | Get specific transaction details |
| `transactions/history/{id}/undo` | POST | Undo a transaction |
| `types/` | GET | List all Gramps type categories |
| `types/default/` | GET | List all default types |
| `types/default/{datatype}` | GET | List default values for a type |
| `types/default/{datatype}/map` | GET | Get type-to-label mapping |
| `types/custom/` | GET | List all custom types |
| `types/custom/{datatype}` | GET/PUT | Get or set custom type values |
| `holidays/` | GET | List available holiday countries |
| `holidays/{country}/{year}/{month}/{day}` | GET | Get holidays for a date |
| `metadata/` | GET | Server metadata (version, features, etc.) |
| `config/` | GET | List configuration keys |
| `config/{key}/` | GET/PUT | Get or set a configuration value |
| `translations/` | GET | List available UI translations |
| `translations/{language}` | GET | Get translations for a language |
| `name-formats/` | GET | Get available name display formats |
| `name-groups/` | GET | Get surname groupings |
| `name-groups/{surname}` | GET | Get group for a surname |
| `name-groups/{surname}/{group}` | PUT | Set group for a surname |
| `bookmarks/` | GET | List bookmark namespaces |
| `bookmarks/{namespace}` | GET/POST | Get or add bookmarks in a namespace |
| `bookmarks/{namespace}/{handle}` | DELETE | Remove a bookmark |
| `filters/` | GET | List filter namespaces |
| `filters/{namespace}` | GET/POST | Get or create filters |
| `filters/{namespace}/{name}` | GET/PUT/DELETE | Manage a specific filter |
| `parsers/dna-match` | POST | Parse DNA match data |
| `chat/` | POST | AI-assisted genealogy chat |
| `users/` | GET | List users (admin) |
| `users/{username}/` | GET/PUT/DELETE | Manage a user |
| `users/{username}/register/` | POST | Register a new user |
| `users/{username}/password/change` | POST | Change password |
| `users/{username}/password/reset/trigger/` | POST | Trigger password reset |
| `users/-/password/reset/` | POST | Complete password reset |
| `users/-/email/confirm/` | POST | Confirm email address |

---

#### Common Query Parameters

**List endpoints** (GET on collection URLs) accept:

| Parameter | Type | Description |
|---|---|---|
| `gramps_id` | string | Filter by Gramps ID (e.g., `I0001`) |
| `page` | int | Page number (0-based) |
| `pagesize` | int | Items per page |
| `sort` | string | Comma-separated sort keys; prefix with `-` for descending |
| `gql` | string | Gramps Query Language filter expression |
| `backlinks` | bool | Include handles of objects that reference this object |
| `extend` | string | Comma-separated list of fields to resolve inline |
| `profile` | string | Comma-separated list of profile summaries to include |
| `strip` | bool | Strip empty/null fields from response |
| `keys` | string | Comma-separated list of fields to include (whitelist) |
| `skipkeys` | string | Comma-separated list of fields to exclude (blacklist) |
| `dates` | string | Date filter: `y/m/d`, `-y/m/d`, `y/m/d-y/m/d`, `y/m/d-` |

**Single-object endpoints** (GET by handle) accept: `backlinks`, `extend`, `profile`, `strip`, `keys`, `skipkeys`.

**`extend` choices** (resolve referenced handles inline):
`all`, `citation_list`, `event_ref_list`, `family_list`, `media_list`, `note_list`, `parent_family_list`, `person_ref_list`, `primary_parent_family`, `tag_list`, `backlinks`

**`profile` choices** (pre-computed summaries):
`all`, `self`, `families`, `events`, `age`, `span`, `ratings`, `references`

**Sort keys** vary by entity type:
- **Sources**: `abbrev`, `author`, `change`, `gramps_id`, `private`, `pubinfo`, `title`
- **Repositories**: `change`, `gramps_id`, `name`, `private`, `type`
- **General**: `gramps_id`, `change`, `private` (available on most types)

---

#### Data Models

##### Person
```json
{
  "handle": "abc123...",
  "gramps_id": "I0001",
  "gender": 1,
  "primary_name": {
    "first_name": "John",
    "surname_list": [{"surname": "Smith", "primary": true, "origintype": {"_class": "NameOriginType", "string": "Inherited"}}],
    "type": {"_class": "NameType", "string": "Birth Name"},
    "suffix": "", "title": "", "nick": "", "call": "", "famnick": ""
  },
  "alternate_names": [],
  "event_ref_list": [{"ref": "<event_handle>", "role": {"_class": "EventRoleType", "string": "Primary"}}],
  "family_list": ["<family_handle>"],
  "parent_family_list": ["<family_handle>"],
  "media_list": [{"ref": "<media_handle>", "rect": [0, 0, 100, 100]}],
  "note_list": ["<note_handle>"],
  "citation_list": ["<citation_handle>"],
  "attribute_list": [{"type": {"_class": "AttributeType", "string": "..."}, "value": "..."}],
  "tag_list": ["<tag_handle>"],
  "urls": [{"type": {"_class": "UrlType", "string": "Web Home"}, "path": "https://...", "desc": "..."}],
  "person_ref_list": [{"ref": "<person_handle>", "rel": "..."}],
  "address_list": [],
  "lds_ord_list": [],
  "private": false,
  "change": 1712477760
}
```
- `gender`: 0=Female, 1=Male, 2=Unknown
- `birth_ref_index` / `death_ref_index`: Indices into `event_ref_list` for birth/death events (read-only, computed by Gramps)

##### Family
```json
{
  "handle": "abc123...",
  "gramps_id": "F0001",
  "father_handle": "<person_handle>",
  "mother_handle": "<person_handle>",
  "child_ref_list": [{"ref": "<person_handle>", "frel": {"_class": "ChildRefType", "string": "Birth"}, "mrel": {"_class": "ChildRefType", "string": "Birth"}}],
  "type": {"_class": "FamilyRelType", "string": "Married"},
  "event_ref_list": [{"ref": "<event_handle>", "role": {"_class": "EventRoleType", "string": "Family"}}],
  "media_list": [], "note_list": [], "citation_list": [], "attribute_list": [], "tag_list": [],
  "private": false
}
```

##### Event
```json
{
  "handle": "abc123...",
  "gramps_id": "E0001",
  "type": {"_class": "EventType", "string": "Birth"},
  "date": {
    "_class": "Date",
    "dateval": [15, 6, 1878, false],
    "quality": 0,
    "modifier": 0,
    "calendar": 0,
    "newyear": 0,
    "sortval": 0,
    "text": ""
  },
  "description": "Born at home",
  "place": "<place_handle>",
  "citation_list": ["<citation_handle>"],
  "media_list": [], "note_list": [], "attribute_list": [], "tag_list": [],
  "private": false
}
```
- **Date.dateval**: `[day, month, year, is_dual_dated]` (day/month 0 = unknown)
- **Date.quality**: 0=regular, 1=estimated, 2=calculated
- **Date.modifier**: 0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, 6=text-only, 7=from, 8=to
- For range/span: `dateval` has 8 elements: `[d1, m1, y1, dual1, d2, m2, y2, dual2]`

##### Place
```json
{
  "handle": "abc123...",
  "gramps_id": "P0001",
  "name": {"value": "Boston", "lang": "", "date": null},
  "alt_names": [{"value": "Beantown"}],
  "place_type": {"_class": "PlaceType", "string": "City"},
  "placeref_list": [{"ref": "<parent_place_handle>", "date": null}],
  "code": "",
  "lat": "42.3601",
  "long": "-71.0589",
  "alt_loc": [],
  "media_list": [], "note_list": [], "citation_list": [], "tag_list": [], "urls": [],
  "private": false
}
```
- `placeref_list`: References to enclosing places (City -> County -> State -> Country)

##### Source
```json
{
  "handle": "abc123...",
  "gramps_id": "S0001",
  "title": "Marriage Register 1875-1880",
  "author": "St. Mary's Church",
  "pubinfo": "Original manuscript",
  "abbrev": "",
  "reporef_list": [{"ref": "<repository_handle>", "call_number": "Vol. 3", "media_type": {"_class": "SourceMediaType", "string": "Book"}}],
  "media_list": [], "note_list": [], "attribute_list": [], "tag_list": [],
  "private": false
}
```

##### Citation
```json
{
  "handle": "abc123...",
  "gramps_id": "C0001",
  "source_handle": "<source_handle>",
  "page": "Page 67, Entry 15",
  "confidence": 2,
  "date": null,
  "media_list": [], "note_list": [], "attribute_list": [], "tag_list": [],
  "private": false
}
```
- `confidence`: 0=very low, 1=low, 2=normal, 3=high, 4=very high

##### Note
```json
{
  "handle": "abc123...",
  "gramps_id": "N0001",
  "type": {"_class": "NoteType", "string": "General"},
  "text": {"_class": "StyledText", "string": "Note content here", "tags": []},
  "format": 0,
  "private": false
}
```
- Text is wrapped in `StyledText` format; `tags` contains inline formatting

##### Media
```json
{
  "handle": "abc123...",
  "gramps_id": "O0001",
  "path": "relative/path/to/file.jpg",
  "mime": "image/jpeg",
  "desc": "Photo of John Smith",
  "checksum": "abc123...",
  "date": null,
  "citation_list": [], "note_list": [], "attribute_list": [], "tag_list": [],
  "private": false
}
```

##### Repository
```json
{
  "handle": "abc123...",
  "gramps_id": "R0001",
  "name": "National Archives",
  "type": {"_class": "RepositoryType", "string": "Archive"},
  "urls": [{"type": {"_class": "UrlType", "string": "Web Home"}, "path": "https://...", "desc": ""}],
  "address_list": [],
  "note_list": [], "tag_list": [],
  "private": false
}
```

##### Tag
```json
{
  "handle": "abc123...",
  "name": "ToDo",
  "color": "#EF2929",
  "priority": 0,
  "change": 1712477760
}
```

##### Common Sub-objects

**EventReference** (in `event_ref_list`):
```json
{"ref": "<event_handle>", "role": {"_class": "EventRoleType", "string": "Primary"}}
```
Roles: `Primary`, `Clergy`, `Celebrant`, `Aide`, `Bride`, `Groom`, `Witness`, `Family`, `Informant`

**ChildReference** (in `child_ref_list`):
```json
{"ref": "<person_handle>", "frel": {"_class": "ChildRefType", "string": "Birth"}, "mrel": {"_class": "ChildRefType", "string": "Birth"}}
```
Relationships: `Birth`, `Adopted`, `Stepchild`, `Sponsored`, `Foster`, `Unknown`

**MediaReference** (in `media_list`):
```json
{"ref": "<media_handle>", "rect": [x1, y1, x2, y2], "citation_list": [], "note_list": [], "attribute_list": []}
```
`rect`: Percentage-based crop rectangle (0-100); empty list = full image

**PlaceReference** (in `placeref_list`):
```json
{"ref": "<parent_place_handle>", "date": null}
```

**RepositoryReference** (in `reporef_list`):
```json
{"ref": "<repository_handle>", "call_number": "...", "media_type": {"_class": "SourceMediaType", "string": "Book"}}
```
Media types: `Book`, `Card`, `Electronic`, `Fiche`, `Film`, `Magazine`, `Manuscript`, `Map`, `Newspaper`, `Photo`, `Tombstone`, `Video`

**URL** (in `urls`):
```json
{"type": {"_class": "UrlType", "string": "Web Home"}, "path": "https://...", "desc": "...", "private": false}
```
Types: `Web Home`, `Web Search`, `FTP`, `E-mail`

**Attribute** (in `attribute_list`):
```json
{"type": {"_class": "AttributeType", "string": "..."}, "value": "...", "citation_list": [], "note_list": [], "private": false}
```

**Address** (in `address_list`):
```json
{"street": "", "locality": "", "city": "", "county": "", "state": "", "country": "", "postal": "", "phone": "", "date": null, "citation_list": [], "note_list": []}
```

**Date** object:
```json
{
  "_class": "Date",
  "dateval": [day, month, year, false],
  "quality": 0,
  "modifier": 0,
  "calendar": 0,
  "newyear": 0,
  "sortval": 0,
  "text": ""
}
```
- `dateval`: `[day, month, year, is_dual_dated]` -- day=0 or month=0 means unknown
- `quality`: 0=regular, 1=estimated, 2=calculated
- `modifier`: 0=regular, 1=before, 2=after, 3=about, 4=range, 5=span, 6=text-only, 7=from, 8=to
- `calendar`: 0=Gregorian, 1=Julian, 2=Hebrew, 3=French Republican, 4=Persian, 5=Islamic, 6=Swedish
- For range/span (modifier 4/5): `dateval` = `[d1, m1, y1, dual1, d2, m2, y2, dual2]`

**Typed enums** (used for `type` fields throughout):
All use the pattern `{"_class": "SomeType", "string": "Value"}`. When creating/updating via MCP tools, pass just the string value (e.g., `"Birth"` for event type).

---

#### GQL (Gramps Query Language) Quick Reference

GQL filters records via the `gql` query parameter on list endpoints.

**Syntax**: `property operator value [and|or property operator value ...]`

**Operators**: `=`, `!=`, `>`, `>=`, `<`, `<=`, `~` (contains), `!~` (not contains), or bare property (truthy check)

**Special properties**: `length` (array size), `any`/`all` (array element predicates), `get_person`/`get_event`/`get_place`/etc. (cross-reference navigation)

**Examples**:
```sql
-- Find people with surname Smith
primary_name.surname_list[0].surname = Smith

-- Find families with 3+ children
child_ref_list.length >= 3

-- Find events in year range
date.dateval[2] > 1850 and date.dateval[2] < 1900

-- Find people born in a specific place
event_ref_list.any.ref.get_event.place.get_place.name.value ~ Boston

-- Find objects with media
media_list.length > 0

-- Find private notes containing text
private and text.string ~ David
```

Full GQL documentation is served as MCP resource `gql://documentation`.

---

#### Current MCP Coverage

**19 registered MCP tools** covering the most common genealogy operations:

| MCP Tool | API Endpoints Used | Status |
|---|---|---|
| `search` | `GET {entity}/` with GQL | Covers all 9 searchable entity types |
| `search_text` | `GET search/` | Full-text search |
| `list_tags` | `GET tags/` | Tag listing with pagination |
| `get` | `GET {entity}/{h}?extend=all` (+ timeline for person/family) | All 9 entity types |
| `upsert_person` | `POST/PUT people/{h}` | Full CRUD, supports `list_mode` |
| `upsert_family` | `POST/PUT families/{h}` | Full CRUD, supports `list_mode` |
| `upsert_event` | `POST/PUT events/{h}` | Full CRUD, supports `list_mode` |
| `upsert_place` | `POST/PUT places/{h}` | Full CRUD, supports `list_mode` |
| `upsert_source` | `POST/PUT sources/{h}` | Full CRUD, supports `list_mode` |
| `upsert_citation` | `POST/PUT citations/{h}` | Full CRUD, supports `list_mode` |
| `upsert_note` | `POST/PUT notes/{h}` | Full CRUD |
| `upsert_media` | `POST/PUT media/{h}` + file upload | Full CRUD, supports `list_mode` |
| `upsert_repository` | `POST/PUT repositories/{h}` | Full CRUD, supports `list_mode` |
| `upsert_tag` | `POST/PUT tags/{h}` | Full CRUD |
| `delete` | `DELETE {entity}/{h}` | All 9 entity types |
| `get_tree_stats` | `GET trees/{tree_id}` | Read-only |
| `get_descendants` | `POST reports/descend_report/file` + task polling | Via report engine |
| `get_ancestors` | `POST reports/ancestor_report/file` + task polling | Via report engine |
| `get_recent_changes` | `GET transactions/history/` | Read-only |

**API endpoints NOT yet exposed as MCP tools** (potential future work):
- `relations/` -- relationship path finding
- `living/` -- living status estimation
- `timelines/people/`, `timelines/families/` -- multi-entity timelines
- `facts/` -- statistical facts
- `events/{h1}/span/{h2}` -- time span calculation
- `exporters/`, `importers/` -- data import/export
- `bookmarks/`, `filters/` -- user bookmarks and saved filters
- `translations/` -- UI translations
- `config/` -- server configuration
- `users/` -- user management
- `metadata/` -- server metadata
- `types/custom/` -- custom type management
- `name-formats/`, `name-groups/` -- name display configuration
- `objects/`, `objects/delete/` -- bulk operations
- `search/index/` -- search index rebuild
- `media/{h}/face_detection`, `media/{h}/ocr` -- AI media analysis
- `media/archive/` -- media archive export/import
- `chat/` -- AI chat
- `transactions/history/{id}/undo` -- undo transactions