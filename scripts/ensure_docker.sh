#!/usr/bin/env bash
# Best-effort Docker setup for gramps-mcp test suite.
#
# Exits 0 if Docker is running and seeded (or was just started + seeded).
# Exits 1 if Docker is unavailable — caller should use `|| true` so pytest
# still runs (conftest auto-skips integration tests when Docker is down).

set -euo pipefail

COMPOSE_FILE="docker-compose.test.yml"
BASE_URL="${GRAMPS_API_URL:-http://localhost:5055}"
PROBE_TIMEOUT=5

# --- Preflight: Docker must be installed and the daemon must be running ---

if ! command -v docker &>/dev/null; then
    echo "[ensure_docker] Docker not installed -- integration tests will be skipped"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "[ensure_docker] Docker daemon not running -- integration tests will be skipped"
    exit 1
fi

# --- Fast path: service already responding and data queryable ---

if curl -sf --max-time "$PROBE_TIMEOUT" "$BASE_URL/" >/dev/null 2>&1; then
    echo "[ensure_docker] Service already responding at $BASE_URL"
    if uv run python scripts/seed_test_db.py --skip-if-seeded --base-url "$BASE_URL"; then
        exit 0
    fi
    # --skip-if-seeded detected unhealthy API (post-cleanup SQLite corruption).
    # Restart the container to clear the bad state, then re-seed.
    echo "[ensure_docker] API unhealthy — restarting containers..."
    docker compose -f "$COMPOSE_FILE" restart --timeout 10
    docker compose -f "$COMPOSE_FILE" up -d --wait
    uv run python scripts/seed_test_db.py --base-url "$BASE_URL"
    exit 0
fi

# --- Cold start: bring up containers and seed ---

echo "[ensure_docker] Starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --wait

echo "[ensure_docker] Seeding test database..."
uv run python scripts/seed_test_db.py --base-url "$BASE_URL"

echo "[ensure_docker] Docker ready"
