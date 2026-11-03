#!/bin/sh
# Build the runtime image, import the server inside it, and run the image's
# own HEALTHCHECK command against a live server.
#
# A venv built on one Python minor version does not load on another, and the
# image still builds fine when that happens (#115). Importing the server is
# the cheapest check that fails on the mismatch. The healthcheck step catches
# a probe that cannot pass, such as one calling a missing binary (#119) or
# targeting an address the server does not bind (#123).
set -eu

image="${1:-gramps-mcp:smoke}"
container="gramps-mcp-smoke-$$"

docker build -t "$image" .
docker run --rm --entrypoint python "$image" -c \
    'import sys, src.gramps_mcp.server; print("import ok on", sys.version.split()[0])'

trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$container" "$image" >/dev/null
probe="$(docker inspect --format '{{index .Config.Healthcheck.Test 1}}' "$image")"
# Reason: the server needs a moment to bind; retry the probe, bounded.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if docker exec "$container" sh -c "$probe" 2>/dev/null; then
        echo "healthcheck ok"
        exit 0
    fi
    sleep 1
done
echo "healthcheck failed: $probe" >&2
docker logs "$container" >&2
exit 1
