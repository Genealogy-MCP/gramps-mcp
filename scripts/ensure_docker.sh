#!/usr/bin/env bash
# Reset-and-seed Docker setup for the gramps-mcp test suite.
#
# Every invocation destroys the test containers and volumes, brings them
# back up, and imports the seed fixture. Write tests no longer clean up
# after themselves (issue #77), so a fresh tree per run is the hermeticity
# guarantee: the suite always starts from the same 2157-person fixture.
#
# grampsweb publishes on an ephemeral host port, so the seed script and the
# test suite read this checkout's URL back from Docker (issue #124).
#
# Exits 0 when Docker is ready and seeded.
# Exits 75 if Docker is unavailable. The caller tolerates only that code, so
# pytest still runs and conftest skips integration tests.
# Any other non-zero exit means this checkout's stack failed to start or
# seed, and `make test` must fail rather than test some other instance.

set -euo pipefail

COMPOSE_FILE="docker-compose.test.yml"
DOCKER_UNAVAILABLE=75

# --- Preflight: Docker must be installed and the daemon must be running ---

if ! command -v docker &>/dev/null; then
    echo "[ensure_docker] Docker not installed -- integration tests will be skipped"
    exit "$DOCKER_UNAVAILABLE"
fi

if ! docker info &>/dev/null; then
    echo "[ensure_docker] Docker daemon not running -- integration tests will be skipped"
    exit "$DOCKER_UNAVAILABLE"
fi

# --- Reset: destroy any previous state, containers and volumes alike ---

echo "[ensure_docker] Resetting containers and volumes..."
docker compose -f "$COMPOSE_FILE" down -v --timeout 10

echo "[ensure_docker] Starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --wait

echo "[ensure_docker] Seeding test database..."
uv run python scripts/seed_test_db.py

echo "[ensure_docker] Docker ready"
