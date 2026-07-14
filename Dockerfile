FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36 AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src/ src/

FROM python:3.14-slim-bookworm@sha256:86f975aca15cf04a40b399eebede9aea7c82eae084d1f1a0a6ef6bcaae871a30

# Add OCI labels
LABEL org.opencontainers.image.title="Gramps MCP"
LABEL org.opencontainers.image.description="AI-Powered Genealogy Research & Management - MCP server for Gramps Web API"
LABEL org.opencontainers.image.url="https://gitlab.com/genealogy-mcp/gramps-mcp"
LABEL org.opencontainers.image.source="https://gitlab.com/genealogy-mcp/gramps-mcp"
LABEL org.opencontainers.image.documentation="https://gitlab.com/genealogy-mcp/gramps-mcp/-/blob/main/README.md"
LABEL org.opencontainers.image.licenses="AGPL-3.0"
LABEL org.opencontainers.image.vendor="Genealogy-MCP"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 gramps && chown -R gramps:gramps /app
USER gramps

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "src.gramps_mcp.server"]
