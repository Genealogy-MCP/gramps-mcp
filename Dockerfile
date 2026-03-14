FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src/ src/

FROM python:3.11-slim-bookworm

# Add OCI labels
LABEL org.opencontainers.image.title="Gramps MCP"
LABEL org.opencontainers.image.description="AI-Powered Genealogy Research & Management - MCP server for Gramps Web API"
LABEL org.opencontainers.image.url="https://github.com/Genealogy-MCP/gramps-mcp"
LABEL org.opencontainers.image.source="https://github.com/Genealogy-MCP/gramps-mcp"
LABEL org.opencontainers.image.documentation="https://github.com/Genealogy-MCP/gramps-mcp/blob/main/README.md"
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
