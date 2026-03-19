"""
Integration tests for MCP server using proper MCP client library.

These tests verify that the MCP server correctly implements the protocol
and can handle real API calls to Gramps Web API endpoints.

The ``mcp_server`` session fixture (conftest.py) auto-starts the server
as a subprocess on a free port.  When Docker is unavailable the fixture
skips, so these tests degrade gracefully in local-only environments.
"""

import subprocess
import sys

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import InitializeResult, TextContent


class TestServerBuild:
    """Test that the server builds and imports correctly."""

    @pytest.mark.asyncio
    async def test_server_starts_without_error(self):
        """Test that the server can start without import errors."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from src.gramps_mcp.server import app; print('Server imports OK')",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.fail(f"Server failed to start: {result.stderr}")

        assert "Server imports OK" in result.stdout


@pytest.mark.server
class TestMCPServerSetup:
    """Test MCP server initialization and setup."""

    @pytest.mark.asyncio
    async def test_server_is_running(self, mcp_server):
        """Test that the MCP server is running and accessible."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_server}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "Gramps MCP Server"

    @pytest.mark.asyncio
    async def test_tool_registration(self, mcp_server):
        """Test that all expected tools are registered."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                result = await session.initialize()
                assert isinstance(result, InitializeResult)
                assert result.serverInfo.name == "gramps"

                tools_result = await session.list_tools()
                tools = tools_result.tools
                # MCP-6: derive expected tools from TOOL_REGISTRY, not hardcoded
                from src.gramps_mcp.server_tools import TOOL_REGISTRY

                registered_tool_names = {tool.name for tool in tools}
                assert registered_tool_names == set(TOOL_REGISTRY.keys())

    @pytest.mark.asyncio
    async def test_tool_descriptions(self, mcp_server):
        """Test that all tools have proper descriptions."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tools = tools_result.tools

                for tool in tools:
                    assert tool.description is not None
                    assert len(tool.description.strip()) > 0
                    assert tool.name is not None


@pytest.mark.server
class TestHTTPRoutes:
    """Test standard HTTP routes."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, mcp_server):
        """Test root endpoint returns server information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_server}/")
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "Gramps MCP Server"
            # MCP-6: derive expected count from TOOL_REGISTRY
            from src.gramps_mcp.server_tools import TOOL_REGISTRY

            assert data["tools_count"] == len(TOOL_REGISTRY)

    @pytest.mark.asyncio
    async def test_health_endpoint(self, mcp_server):
        """Test health check endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_server}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "Gramps MCP Server"


@pytest.mark.server
class TestMCPProtocolCompliance:
    """Test MCP protocol compliance and communication."""

    @pytest.mark.asyncio
    async def test_mcp_tools_list_request(self, mcp_server):
        """Test MCP tools/list request."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                result = await session.initialize()
                assert isinstance(result, InitializeResult)

                tools_result = await session.list_tools()
                # MCP-6: derive expected count from TOOL_REGISTRY
                from src.gramps_mcp.server_tools import TOOL_REGISTRY

                assert len(tools_result.tools) == len(TOOL_REGISTRY)

    @pytest.mark.asyncio
    async def test_mcp_tool_call_search_real_api(self, mcp_server):
        """Test search tool call with real API integration."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search",
                    {
                        "arguments": {
                            "type": "person",
                            "gql": 'primary_name.first_name ~ "John"',
                            "max_results": 20,
                        }
                    },
                )

                assert len(result.content) >= 1
                assert isinstance(result.content[0], TextContent)

                response_text = result.content[0].text
                assert (
                    "Found" in response_text
                    or "no people found" in response_text.lower()
                    or "not found" in response_text.lower()
                )

    @pytest.mark.asyncio
    async def test_mcp_invalid_tool_call(self, mcp_server):
        """Test MCP server handles invalid tool calls properly."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                try:
                    result = await session.call_tool("non_existent_tool", {})
                    assert len(result.content) >= 1
                    assert isinstance(result.content[0], TextContent)
                    response_text = result.content[0].text.lower()
                    assert "error" in response_text or "not found" in response_text
                except Exception as e:
                    error_str = str(e).lower()
                    assert "non_existent_tool" in error_str or "not found" in error_str


@pytest.mark.server
class TestToolIntegrationRealAPI:
    """Test tool integration with real Gramps Web API."""

    @pytest.mark.asyncio
    async def test_search_with_specific_query(self, mcp_server):
        """Test search tool with specific query."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search",
                    {
                        "arguments": {
                            "type": "person",
                            "gql": 'primary_name.surname_list.any.surname ~ "Smith"',
                            "max_results": 20,
                        }
                    },
                )

                assert len(result.content) >= 1
                assert isinstance(result.content[0], TextContent)
                response_text = result.content[0].text
                assert len(response_text.strip()) > 0

    @pytest.mark.asyncio
    async def test_search_all_objects(self, mcp_server):
        """Test search_text tool for comprehensive search."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search_text", {"arguments": {"query": "test", "pagesize": 3}}
                )

                assert len(result.content) >= 1
                assert isinstance(result.content[0], TextContent)


@pytest.mark.server
class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_tree_id(self, mcp_server):
        """Test handling of invalid tree ID."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "search",
                    {
                        "arguments": {
                            "type": "person",
                            "gql": 'primary_name.first_name ~ "test"',
                            "max_results": 1,
                        }
                    },
                )

                assert len(result.content) >= 1
                assert isinstance(result.content[0], TextContent)

    @pytest.mark.asyncio
    async def test_get_details_invalid_handle(self, mcp_server):
        """Test get with invalid handle."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "get",
                    {"arguments": {"type": "person", "handle": "invalid_handle_123"}},
                )

                assert len(result.content) >= 1
                assert isinstance(result.content[0], TextContent)
                response_text = result.content[0].text
                assert len(response_text.strip()) > 0


class TestParameterModels:
    """Test that server uses proper parameter models from parameters module."""

    def test_server_imports_parameter_models(self):
        """Test that server can import from src.gramps_mcp.models.parameters."""
        from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
        from src.gramps_mcp.models.parameters.people_params import PersonData
        from src.gramps_mcp.models.parameters.search_params import SearchParams

        assert hasattr(SearchParams, "model_fields")
        assert hasattr(PersonData, "model_fields")
        assert hasattr(FamilySaveParams, "model_fields")

        assert "query" in SearchParams.model_fields
        assert "pagesize" in SearchParams.model_fields
        assert "primary_name" in PersonData.model_fields
        assert "handle" in FamilySaveParams.model_fields


@pytest.mark.server
class TestMCPResources:
    """Test MCP resource functionality."""

    @pytest.mark.asyncio
    async def test_list_resources(self, mcp_server):
        """Test that resources are properly registered."""
        endpoint = f"{mcp_server}/mcp"

        async with streamable_http_client(endpoint) as client_streams:
            read_stream, write_stream, _ = client_streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                resources_result = await session.list_resources()
                resources = resources_result.resources

                resource_uris = {str(resource.uri) for resource in resources}
                assert "gql://documentation" in resource_uris
