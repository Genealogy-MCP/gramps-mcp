# Gramps MCP - AI-Powered Genealogy Research & Management

[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](./LICENSE) [![Python](https://img.shields.io/badge/Python-3.11+-brightgreen)](https://python.org) [![MCP](https://img.shields.io/badge/MCP-1.2.0+-orange)](https://modelcontextprotocol.io) [![pipeline status](https://gitlab.com/genealogy-mcp/gramps-mcp/badges/main/pipeline.svg)](https://gitlab.com/genealogy-mcp/gramps-mcp/-/pipelines)

**Note:** GitHub is a read-only mirror. Development happens on [GitLab](https://gitlab.com/genealogy-mcp/gramps-mcp).

## Without Gramps MCP

Genealogy research with AI assistants is limited and frustrating:

- No direct access to your family tree data
- Manual data entry and research across multiple platforms
- Generic genealogy advice without context of your specific family
- No ability to automatically update or maintain your research

## With Gramps MCP

Gramps MCP provides AI assistants with direct access to your Gramps genealogy database through a comprehensive set of tools. Your AI assistant can now:

- **Smart Search**: Find people, families, events, places, and sources across your entire database
- **Data Management**: Create and update genealogy records with proper validation
- **Tree Analysis**: Trace descendants, ancestors, and family connections
- **Relationship Discovery**: Explore family connections and research gaps
- **Tree Information**: Get comprehensive tree statistics and track changes

Add Gramps MCP to your AI assistant and transform how you research family history:

```txt
Search for all descendants of John Smith born in Ireland before 1850
```

```txt
Create a new person record for Mary O'Connor with birth date 1823 in County Cork
```

```txt
Find all families missing marriage dates and suggest research priorities
```

No more manual data entry, no context switching between apps, no generic genealogy advice.

- Connect to your Gramps Web API
- Install Gramps MCP in your AI assistant
- Start intelligent genealogy research with natural language

## Features

### Code Mode Architecture: 2 Tools, 22 Operations

Gramps MCP uses a **Code Mode** architecture: just 2 MCP tools (`search` + `execute`) that provide progressive disclosure of 22 operations. This reduces LLM context window overhead from ~19K tokens to ~1K tokens.

- **`search`** - Discover available operations by keyword (e.g., "find people", "create event", "delete")
- **`execute`** - Run a named operation with parameters (e.g., `execute("upsert_person", {...})`)

#### Available Operations (22)

| Category | Operations |
|----------|-----------|
| **Search** (3) | `search` (GQL queries), `search_text` (full-text), `list_tags` |
| **Read** (4) | `get` (entity details), `get_tree_stats`, `download_media`, `list_backups` |
| **Write** (11) | `upsert_person`, `upsert_family`, `upsert_event`, `upsert_place`, `upsert_source`, `upsert_citation`, `upsert_note`, `upsert_media`, `upsert_repository`, `upsert_tag`, `create_backup` |
| **Delete** (1) | `delete` (any entity type) |
| **Analysis** (3) | `get_ancestors`, `get_descendants`, `get_recent_changes` |

#### Backups

`create_backup` stores a backup of the tree on the Gramps Web server; `list_backups` shows the stored backups, newest first. Restore, download and delete are not exposed; use the Gramps Web UI or the API for those. Both operations need:

- gramps-webapi 3.24 or later (older servers answer 404)
- a backup directory configured on the server (`BACKUP_DIR`; without it the server answers 501)
- an account with the Owner role or above (the ManageBackups permission)

An archive holds the tree, its settings and the user list without credentials. It holds no media files. Archives live on the server's disk, not on the machine running the MCP server. The server keeps only its configured number of newest backups per tree (`BACKUP_KEEP`) and prunes older ones after every create, and it rate-limits backup creation per tree.

## Installation

### Requirements

- **Gramps Web API 3.x** (shipped with Gramps Web 26.x / Gramps 6.0 or later) - [Setup Guide](https://www.grampsweb.org/install_setup/setup/)
- Docker and Docker Compose
- MCP-compatible AI assistant (Claude Desktop, Cursor, etc.)

> **Compatibility:** Gramps Web 25.x and earlier (API 2.x / Gramps 5.2) are not supported. If you are running an older version, upgrade to Gramps Web 26.x before using this server.

### Quick Start

1. **Ensure Gramps Web is Running**:
   - Follow the [Gramps Web setup guide](https://www.grampsweb.org/install_setup/setup/) to get your family tree online
   - Note your Gramps Web URL, username, and password
   - Find your tree ID under System Information in your Gramps Web interface

2. **Start the Server**:

```bash
# Download the configuration
curl -O https://gitlab.com/genealogy-mcp/gramps-mcp/-/raw/main/docker-compose.yml
curl -O https://gitlab.com/genealogy-mcp/gramps-mcp/-/raw/main/.env.example
cp .env.example .env
# Edit .env with your Gramps Web API credentials

# Start the server
docker-compose up -d
```

That's it! The MCP server will be running at `http://localhost:8000/mcp`

The image sets `GRAMPS_MCP_HOST=0.0.0.0`, so the server listens on every container interface and the published port reaches it. Run outside Docker, the server binds `127.0.0.1` unless you set `GRAMPS_MCP_HOST` yourself. The server has no authentication of its own, so `docker-compose.yml` publishes the port on loopback only (`"127.0.0.1:8000:8000"`). Change it to `"8000:8000"` only behind a firewall or an authenticating reverse proxy.

`/mcp` accepts only a localhost `Host` header and answers any other with HTTP 421, which guards against DNS rebinding. A reverse proxy that forwards its public hostname, or a compose service calling `http://gramps-mcp:8000/mcp`, needs that host in `GRAMPS_MCP_ALLOWED_HOSTS`, a comma-separated list such as `gramps-mcp:8000,mcp.example.com`. An entry ending in `:*` matches any port.

### Alternative: Run Without Docker

If you prefer to run the server directly with Python:

1. **Setup Python Environment**:
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

2. **Run the Server**:
```bash
# HTTP transport (for web-based MCP clients)
uv run python -m src.gramps_mcp.server

# Stdio transport (for CLI-based MCP clients)
uv run python -m src.gramps_mcp.server stdio
```

The HTTP server will be available at `http://localhost:8000/mcp`, while stdio runs directly in the terminal.

### Environment Configuration

Create a `.env` file with your Gramps Web settings:

```bash
# Your Gramps Web instance (from step 1)
GRAMPS_API_URL=https://your-gramps-web-domain.com  # Without /api suffix - will be added automatically
GRAMPS_USERNAME=your-gramps-web-username
GRAMPS_PASSWORD=your-gramps-web-password
GRAMPS_TREE_ID=your-tree-id  # Find this under System Information in Gramps Web
```

## MCP Client Configuration

### Claude Desktop

Add to your Claude Desktop MCP configuration file (`claude_desktop_config.json`):

**Using Docker** (works with both pre-built and local images):
```json
{
  "mcpServers": {
    "gramps": {
      "command": "docker",
      "args": ["exec", "-i", "gramps-mcp-gramps-mcp-1", "python", "-m", "src.gramps_mcp.server", "stdio"]
    }
  }
}
```

**Using uv directly** (if running without Docker):
```json
{
  "mcpServers": {
    "gramps": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.gramps_mcp.server", "stdio"],
      "cwd": "/path/to/gramps-mcp"
    }
  }
}
```

### OpenWebUI

OpenWebUI recommends using the [mcpo proxy](https://docs.openwebui.com/openapi-servers/mcp/) to expose MCP servers as OpenAPI endpoints.

**With uv:**
```bash
uvx mcpo --port 8000 -- uv run python -m src.gramps_mcp.server stdio
```

**With Docker:**
```bash
uvx mcpo --port 8000 -- docker exec -i gramps-mcp-gramps-mcp-1 uv run python -m src.gramps_mcp.server stdio
```

### Claude Code

**HTTP Transport:**
```bash
claude mcp add --transport http gramps http://localhost:8000/mcp
```

**Stdio Transport** (direct connection, more efficient):
```bash
# Using Docker
claude mcp add --transport stdio gramps "docker exec -i gramps-mcp-gramps-mcp-1 sh -c 'cd /app && python -m src.gramps_mcp.server stdio'"

# Using uv directly (requires local setup)
claude mcp add --transport stdio gramps "uv run python -m src.gramps_mcp.server stdio"
```

> **Transport Choice:** Use **stdio** for better performance and direct integration with CLI tools like Claude Code. Use **HTTP** when you need the server to handle multiple clients or prefer web-based access.

### Other MCP Clients

For any other MCP client, use the HTTP transport endpoint:

```json
{
  "mcpServers": {
    "gramps": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Development

### Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose (for integration tests)

### Setup

```bash
git clone https://gitlab.com/genealogy-mcp/gramps-mcp.git
cd gramps-mcp
make install
```

### Running Tests

```bash
# Unit tests only (no Docker needed, fast)
make test-unit

# Full integration tests (starts Docker, seeds data, runs all tests, tears down)
make test-integration

# Full CI pipeline (lint + typecheck + test + audit)
make ci
```

Integration tests use an ephemeral local Gramps Web instance via Docker Compose.
The test fixture (`tests/fixtures/seed.gramps`) contains 2,157 people from the
Gramps project's example dataset. Run `make help` to see all available targets.

### Manual Docker Control

```bash
make docker-up     # Start test containers
make docker-seed   # Seed with fixture data
make docker-down   # Stop and remove containers
```

## Architecture

### Core Components

```
src/gramps_mcp/
|-- server.py           # MCP server (2 meta-tools: search + execute)
|-- operations.py       # Operation registry (handwritten + table-built entries)
|-- overlays.py         # Per-entity read policy: read routes, read/delete op overlays
|-- write_overlays.py   # Per-entity write policy: bindings and upsert op overlays
|-- write_hooks.py      # Write hooks: reference checks, media upload, tag reply
|-- registry_build.py   # Builds and merges registry entries from the resource table
|-- resource_table.py   # Generated entity resource table (OpenAPI snapshot)
|-- client.py           # Gramps Web API client
|-- auth.py             # JWT authentication
|-- config.py           # Configuration management
|-- tools/              # Operation handlers ('search'/'execute' meta-tools come from mcp-codemode)
|   |-- search_basic.py    # GQL search + text search handlers
|   |-- search_details.py  # Entity detail handlers
|   |-- upsert_table.py    # Generic upsert (all ten entities)
|   |-- data_management_delete.py # Delete handler
|   |-- data_management_media.py  # Media download handler
|   |-- backups.py         # Backup handlers
|   `-- analysis.py        # Tree analysis handlers
|-- handlers/           # Data formatting handlers
`-- models/             # Pydantic data models
```

### Technology Stack

- **MCP Python SDK**: Model Context Protocol implementation
- **FastAPI**: HTTP server for MCP transport
- **Pydantic**: Data validation and serialization
- **httpx**: Async HTTP client for API communication
- **PyJWT**: JWT token authentication
- **python-dotenv**: Environment configuration


## Usage Examples

### Basic Search Operations

```txt
Find all people with the surname "Smith" born in Ireland
```

```txt
Show me recent changes to the family tree in the last 30 days
```

### Data Creation and Updates

```txt
Create a new person record for Patrick O'Brien, born 1845 in Cork, Ireland
```

```txt
Add a marriage event for John and Mary Smith on June 15, 1870 in Boston
```

### Genealogy Analysis

```txt
Find all descendants of Margaret Kelly and show their birth locations
```


### Tree Information & Statistics

```txt
Show me statistics about my family tree - how many people, families, and events
```

```txt
What recent changes have been made to my family tree in the last week?
```

## Security

- JWT token authentication with automatic refresh
- Environment-based credential management
- Input validation using Pydantic models
- Secure HTTP transport with proper error handling
- No sensitive data exposed in tool responses


## Troubleshooting

### Common Issues

**Connection refused errors**: Ensure your Gramps Web API server is running and accessible at the configured URL.

**Authentication failures**: Verify your username and password are correct and the user has appropriate permissions.

**Tool timeout errors**: Check your network connection and consider increasing timeout values for large datasets.

**Docker issues**: Ensure Docker and Docker Compose are installed and running.

### Debug Mode

To enable debug logging, check your application logs with:

```bash
docker-compose logs -f
```

## License

This project is a fork of [gramps-mcp](https://github.com/caboutme/gramps-mcp) by **cabout.me**, licensed under the [GNU Affero General Public License v3.0](./LICENSE). We are grateful to cabout.me for open-sourcing the original project and making this work possible. All source files in `src/` and `scripts/` carry AGPL copyright headers attributing the original and fork authors as required by the license.

## Related Projects

- [Gramps](https://gramps-project.org/) - Free genealogy software
- [Gramps Web API](https://github.com/gramps-project/gramps-web-api) - Web API for Gramps
- [Model Context Protocol](https://modelcontextprotocol.io/) - Standard for AI tool integration

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Setting up the development environment
- Running tests and maintaining code quality
- Submitting pull requests
- Reporting issues and requesting features

### Community & Support

- **Bug Reports & Feature Requests**: [GitLab Issues](https://gitlab.com/genealogy-mcp/gramps-mcp/-/issues)
- **Questions & Discussions**: [GitLab Issues](https://gitlab.com/genealogy-mcp/gramps-mcp/-/issues)
- **Documentation**: [Project Wiki](https://gitlab.com/genealogy-mcp/gramps-mcp/-/wikis/home)

## Acknowledgments

- [cabout.me](https://github.com/caboutme/gramps-mcp) for creating and open-sourcing the original gramps-mcp project
- The Gramps Project team for creating excellent genealogy software
- Anthropic for developing the Model Context Protocol
- The genealogy research community for inspiration and feedback