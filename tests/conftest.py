"""
Shared test fixtures for Gramps MCP integration tests.

The suite assumes a freshly seeded Docker instance (ensure_docker.sh resets
and reseeds before every `make test` run); there is no per-entity cleanup.
"""

import logging
import os
import re
import socket
import subprocess
import sys
import time
from unittest.mock import AsyncMock

import pytest

from src.gramps_mcp.auth import AuthManager
from tests._test_env import DEFAULT_API_URL as _DEFAULT_API_URL
from tests._test_env import resolve_test_env


def _is_docker_reachable(url: str) -> bool:
    """Check if the local Gramps Web Docker instance is responding.

    Args:
        url: Base URL to probe (e.g. http://localhost:5055).

    Returns:
        True if the service responds with HTTP 200.
    """
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"{url}/", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def pytest_configure(config: pytest.Config) -> None:
    """Point the suite at a Gramps instance before collection or imports.

    An explicit GRAMPS_API_URL keeps its inherited credentials. Without one
    the local Docker seed is the target, and inherited credentials are
    dropped rather than paired with a URL they do not belong to.
    """
    updates, ignored = resolve_test_env(os.environ)
    os.environ.update(updates)

    target = os.environ["GRAMPS_API_URL"]
    is_default = target == _DEFAULT_API_URL
    suffix = " (local Docker defaults)" if is_default else ""
    print(f"\nGramps MCP Tests — targeting: {target}{suffix}\n")
    if ignored:
        print(
            f"Ignoring inherited {', '.join(ignored)}: no GRAMPS_API_URL was set, "
            f"so the suite uses the {_DEFAULT_API_URL} seed credentials. "
            "Export GRAMPS_API_URL to target another instance.\n"
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Auto-skip integration tests when Docker is unreachable.

    In CI (REQUIRE_INTEGRATION=1), integration tests FAIL instead of skipping.
    Locally (default), they skip with a warning if Docker is down.
    """
    require = os.environ.get("REQUIRE_INTEGRATION", "").strip()
    target = os.environ.get("GRAMPS_API_URL", _DEFAULT_API_URL)

    if _is_docker_reachable(target):
        return

    if require == "1":
        pytest.fail(
            f"REQUIRE_INTEGRATION=1 but Gramps Web at {target} is unreachable. "
            "Start Docker with: make docker-up && make docker-seed",
            pytrace=False,
        )

    skip_marker = pytest.mark.skip(
        reason=f"Gramps Web at {target} is unreachable (run: make test)"
    )
    for item in items:
        if "integration" in item.keywords or "server" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session", autouse=True)
def shared_auth_session():
    """Authenticate once at session start; integration tests share the token.

    The old per-test reset_auth_singleton fixture destroyed the cached JWT
    before every test, forcing re-authentication.  With ~500 tests the
    /api/token/ rate limiter (429) triggered after the first few requests,
    cascading failures across the entire integration suite.

    This session-scoped fixture lets the singleton persist so the token is
    reused.  A single reset at session end prevents state leakage to other
    pytest sessions.  Unit tests are unaffected because they mock the
    client and never call AuthManager.authenticate().
    """
    yield
    AuthManager.reset_instance()


def _find_free_port() -> int:
    """Find an available TCP port on localhost.

    Returns:
        An unused port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_MCP_SERVER_STARTUP_TIMEOUT = 15  # seconds


@pytest.fixture(scope="session")
def mcp_server():
    """Start MCP server as a subprocess for E2E server tests.

    Finds a free port, starts the server process, polls /health until ready,
    yields the base URL, and terminates the process on teardown.
    Auto-skips if the Gramps Web Docker instance is unreachable.

    Yields:
        str: Base URL of the running MCP server (e.g. http://localhost:12345).
    """
    import urllib.error
    import urllib.request

    target = os.environ.get("GRAMPS_API_URL", _DEFAULT_API_URL)
    if not _is_docker_reachable(target):
        pytest.skip("Gramps Web API unreachable -- cannot start MCP server")

    port = _find_free_port()
    env = {**os.environ, "GRAMPS_MCP_PORT": str(port)}

    proc = subprocess.Popen(
        [sys.executable, "-m", "src.gramps_mcp.server"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_url = f"http://localhost:{port}"
    deadline = time.monotonic() + _MCP_SERVER_STARTUP_TIMEOUT

    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            pytest.fail(f"MCP server exited with code {proc.returncode}: {stderr}")
        try:
            urllib.request.urlopen(f"{base_url}/health", timeout=1)
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    else:
        proc.terminate()
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(
            f"MCP server not healthy within {_MCP_SERVER_STARTUP_TIMEOUT}s: {stderr}"
        )

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


logger = logging.getLogger(__name__)

TEST_PREFIX = "MCP_TEST_"


def extract_handle(text: str) -> str:
    """Extract hex handle from tool response text.

    Args:
        text: Tool response text containing a handle in [handle] format.

    Returns:
        The extracted handle string.
    """
    match = re.search(r"\[([a-f0-9]+)\]", text)
    if not match:
        pytest.fail(f"Could not extract handle from: {text}")
    return match.group(1)


def _mock_client(responses):
    """Create a mock client returning predefined responses by API call name.

    Keys should be enum names like "GET_NOTE", "GET_SOURCE", etc.
    Values can be a dict (same response every time) or a list of dicts
    (returns each in sequence, repeating the last for extra calls).
    """
    client = AsyncMock()
    call_count = {}

    async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
        key = api_call.name if hasattr(api_call, "name") else str(api_call)
        call_count.setdefault(key, 0)
        if key in responses:
            val = responses[key]
            if isinstance(val, list):
                idx = min(call_count[key], len(val) - 1)
                call_count[key] += 1
                return val[idx]
            return val
        return {}

    client.make_api_call = AsyncMock(side_effect=mock_api_call)
    return client
