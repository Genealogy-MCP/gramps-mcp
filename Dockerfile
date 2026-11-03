# Reason: one image for both stages. A venv only runs on the interpreter that
# built it (site-packages path and compiled wheel ABI), so the builder and the
# runtime must never drift apart (#115).
ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f

FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM ${PYTHON_IMAGE} AS builder

COPY --from=uv /uv /bin/uv

# Build the venv on the image's own interpreter, never a uv-managed download.
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src/ src/

FROM ${PYTHON_IMAGE}

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

# Reason: the server defaults to loopback (MCP-20), which a published port
# cannot reach. The container's network namespace is the isolation here (#118).
ENV GRAMPS_MCP_HOST=0.0.0.0

RUN useradd -m -u 1000 gramps && chown -R gramps:gramps /app
USER gramps

EXPOSE 8000

# Reason: probe 127.0.0.1, not localhost. localhost can resolve to ::1 first,
# and the server binds IPv4 only, so each probe paid a refused IPv6 connect
# before falling back. The urlopen timeout stays under the Docker timeout so a
# hung server fails the probe instead of Docker killing it (#123). The shell
# expands GRAMPS_MCP_PORT at probe time, with the server's own default (#125).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${GRAMPS_MCP_PORT:-8000}/health', timeout=2)" || exit 1

CMD ["python", "-m", "src.gramps_mcp.server"]
