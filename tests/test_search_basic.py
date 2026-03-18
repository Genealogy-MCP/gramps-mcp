"""
Integration tests for basic search tools using real Gramps API.

Tests search_people, search_families, search_events, search_places,
search_sources, search_media, and search_all tools.
"""

import pytest
from mcp.types import TextContent

from src.gramps_mcp.tools.search_basic import (
    search_text_tool,
    search_tool,
)

pytestmark = pytest.mark.integration


class TestFindPersonTool:
    """Test search_tool functionality for person with real API."""

    @pytest.mark.asyncio
    async def test_find_person(self):
        """Test people search with GQL."""
        result = await search_tool(
            {
                "type": "person",
                "gql": 'primary_name.first_name ~ "John"',
                "max_results": 3,
            }
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected results for 'John' in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindFamilyTool:
    """Test search_tool functionality for family with real API."""

    @pytest.mark.asyncio
    async def test_find_family(self):
        """Test families search with GQL."""
        result = await search_tool(
            {
                "type": "family",
                "gql": 'father_handle.get_person.primary_name.surname_list.any.surname ~ "Smith"',
                "max_results": 3,
            }
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected results for 'Smith' families in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindEventTool:
    """Test search_tool functionality for event with real API."""

    @pytest.mark.asyncio
    async def test_find_event(self):
        """Test events search with GQL."""
        result = await search_tool(
            {"type": "event", "gql": "date.dateval[2] > 1800", "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected events after 1800 in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindPlaceTool:
    """Test search_tool functionality for place with real API."""

    @pytest.mark.asyncio
    async def test_find_place(self):
        """Test places search with GQL."""
        result = await search_tool(
            {"type": "place", "gql": 'name.value ~ "Boston"', "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected Boston in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindSourceTool:
    """Test search_tool functionality for source with real API."""

    @pytest.mark.asyncio
    async def test_find_source(self):
        """Test sources search with GQL."""
        result = await search_tool(
            {"type": "source", "gql": 'title ~ "Baptize"', "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected baptism sources in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindRepositoryTool:
    """Test search_tool functionality for repository with real API."""

    @pytest.mark.asyncio
    async def test_find_repository(self):
        """Test repositories search with GQL."""
        result = await search_tool(
            {"type": "repository", "gql": 'name ~ "Library"', "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected library repositories in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindCitationTool:
    """Test search_tool functionality for citation with real API."""

    @pytest.mark.asyncio
    async def test_find_citation(self):
        """Test citations search with GQL."""
        result = await search_tool(
            {"type": "citation", "gql": 'page ~ "1624"', "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected citations with '1624' in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindMediaTool:
    """Test search_tool functionality for media with real API."""

    @pytest.mark.asyncio
    async def test_find_media(self):
        """Test media search with GQL."""
        result = await search_tool(
            {"type": "media", "gql": 'desc ~ "birth record"', "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected birth record media in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindNoteTool:
    """Test search_tool functionality for note with real API."""

    @pytest.mark.skip(
        reason="Gramps Web GQL engine still crashes on note queries "
        "in API 3.x (HTTP 500 on any note GQL filter)"
    )
    @pytest.mark.asyncio
    async def test_find_note(self):
        """Test notes search with GQL."""
        result = await search_tool(
            {"type": "note", "gql": 'gramps_id ~ "N0001"', "max_results": 3}
        )

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text, (
            f"Expected notes in seeded database but got: {result[0].text}"
        )

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"


class TestFindAnythingTool:
    """Test search_text_tool functionality with real API."""

    @pytest.mark.asyncio
    async def test_find_anything(self):
        """Test search across all object types with query."""
        result = await search_text_tool({"query": "Warner", "max_results": 3})

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "error" not in result[0].text.lower(), (
            f"Error found in response: {result[0].text}"
        )
        assert "Found" in result[0].text and "records matching" in result[0].text

        result_count = result[0].text.count("* **")
        assert result_count <= 3, f"Expected max 3 results, got {result_count}"
