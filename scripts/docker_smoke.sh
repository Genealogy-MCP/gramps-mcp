#!/bin/sh
# Build the runtime image and import the server inside it.
#
# A venv built on one Python minor version does not load on another, and the
# image still builds fine when that happens (#115). Importing the server is
# the cheapest check that fails on the mismatch.
set -eu

image="${1:-gramps-mcp:smoke}"

docker build -t "$image" .
docker run --rm --entrypoint python "$image" -c \
    'import sys, src.gramps_mcp.server; print("import ok on", sys.version.split()[0])'
