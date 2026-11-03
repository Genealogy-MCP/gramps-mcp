#!/bin/sh
# Build the runtime image, import the server inside it, run the image's own
# HEALTHCHECK command against a live server, and reach /health from outside
# the container.
#
# A venv built on one Python minor version does not load on another, and the
# image still builds fine when that happens (#115). Importing the server is
# the cheapest check that fails on the mismatch. The healthcheck step catches
# a probe that cannot pass, such as one calling a missing binary (#119) or
# targeting an address the server does not bind (#123).
#
# A server bound to the container's loopback passes its own HEALTHCHECK but
# not the published port (#118). Probing from a second container over the
# bridge network fails on that bind, on a local daemon and on CI dind alike.
#
# The server runs on a non-default GRAMPS_MCP_PORT, so a probe that hardcodes
# the default port fails here (#125).
set -eu

image="${1:-gramps-mcp:smoke}"
container="gramps-mcp-smoke-$$"
port=8123

docker build -t "$image" .
docker run --rm --entrypoint python "$image" -c \
    'import sys, src.gramps_mcp.server; print("import ok on", sys.version.split()[0])'

trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
# Reason: the server reads its settings before binding and exits without
# them (#121). Port 9 refuses the login fast, which startup logs and survives.
docker run -d --name "$container" \
    -e GRAMPS_API_URL=http://127.0.0.1:9 \
    -e GRAMPS_USERNAME=smoke \
    -e GRAMPS_PASSWORD=smoke \
    -e GRAMPS_MCP_PORT="$port" \
    "$image" >/dev/null
probe="$(docker inspect --format '{{index .Config.Healthcheck.Test 1}}' "$image")"
# Reason: the server needs a moment to bind; retry the probe, bounded.
healthy=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if docker exec "$container" sh -c "$probe" 2>/dev/null; then
        echo "healthcheck ok"
        healthy=1
        break
    fi
    sleep 1
done
if [ "$healthy" -ne 1 ]; then
    echo "healthcheck failed: $probe" >&2
    # Reason: retries hide the probe's stderr; show it once so a missing binary
    # (#119) reads differently from a refused connection (#123).
    docker exec "$container" sh -c "$probe" || true
    docker logs "$container" >&2
    exit 1
fi

ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container")
if docker run --rm --entrypoint python "$image" -c \
    'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=5)' \
    "http://$ip:$port/health"; then
    echo "published port ok at $ip:$port"
    exit 0
fi
echo "server unreachable from outside its container at $ip:$port" >&2
docker logs "$container" >&2
exit 1
