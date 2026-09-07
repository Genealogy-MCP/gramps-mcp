#!/usr/bin/env bash
# Reset-and-seed Docker setup for the gramps-mcp test suite.
#
# Every invocation destroys the test containers and volumes, brings them
# back up, and imports the seed fixture. Write tests no longer clean up
# after themselves (issue #77), so a fresh tree per run is the hermeticity
# guarantee: the suite always starts from the same 2157-person fixture.
#
# Exits 0 when Docker is ready and seeded.
# Exits 1 if Docker is unavailable — caller should use `|| true` so pytest
# still runs (conftest auto-skips integration tests when Docker is down).

set -euo pipefail

COMPOSE_FILE="docker-compose.test.yml"
BASE_URL="${GRAMPS_API_URL:-http://localhost:5055}"

# --- Preflight: Docker must be installed and the daemon must be running ---

if ! command -v docker &>/dev/null; then
    echo "[ensure_docker] Docker not installed -- integration tests will be skipped"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "[ensure_docker] Docker daemon not running -- integration tests will be skipped"
    exit 1
fi

# --- Reset: destroy any previous state, containers and volumes alike ---

echo "[ensure_docker] Resetting containers and volumes..."
docker compose -f "$COMPOSE_FILE" down -v --timeout 10

echo "[ensure_docker] Starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --wait

echo "[ensure_docker] Seeding test database..."
uv run python scripts/seed_test_db.py --base-url "$BASE_URL"

echo "[ensure_docker] Docker ready"
