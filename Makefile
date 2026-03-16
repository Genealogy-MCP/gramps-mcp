.DEFAULT_GOAL := help

.PHONY: help install lint format typecheck test test-unit test-verbose test-server test-integration coverage audit clean pre-commit run run-stdio ci docker-up docker-down docker-seed

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (including dev)
	uv sync --group dev
	uv run pre-commit install

lint: ## Run linter and format check
	uv run ruff check src/
	uv run ruff format --check src/

format: ## Auto-format source code
	uv run ruff format src/
	uv run ruff check --fix src/

typecheck: ## Run pyright type checker
	uv run pyright src/

test: ## Run all tests (requires Docker for integration tests)
	uv run pytest

test-unit: ## Run unit tests only (no Docker needed)
	uv run pytest -m "not integration" --cov-fail-under=60

test-verbose: ## Run tests with verbose output
	uv run pytest -xvs

test-server: ## Run e2e tests requiring a running MCP server
	uv run pytest -m server -xvs

test-integration: ## Start Docker, seed, run ALL tests, teardown
	docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
	docker compose -f docker-compose.test.yml up -d --wait
	uv run python scripts/seed_test_db.py || \
		{ docker compose -f docker-compose.test.yml down -v; exit 1; }
	uv run pytest; rc=$$?; \
		docker compose -f docker-compose.test.yml down -v; \
		exit $$rc

docker-up: ## Start Gramps Web test containers
	docker compose -f docker-compose.test.yml up -d --wait

docker-down: ## Stop and remove test containers and volumes
	docker compose -f docker-compose.test.yml down -v

docker-seed: ## Seed the running test instance with fixture data
	uv run python scripts/seed_test_db.py

coverage: ## Generate HTML coverage report
	uv run pytest --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

audit: ## Audit dependencies for known vulnerabilities
	uv run pip-audit

pre-commit: ## Run all pre-commit hooks
	uv run pre-commit run --all-files

clean: ## Remove build artifacts and caches
	rm -rf .coverage htmlcov/ .mypy_cache/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

run: ## Run MCP server (streamable-http on port 8000)
	uv run python -m src.gramps_mcp.server

run-stdio: ## Run MCP server with stdio transport
	uv run python -m src.gramps_mcp.server stdio

ci: lint typecheck test audit ## Run full CI pipeline locally
