"""
Tests for utility functions.
"""

import asyncio

import pytest
from dotenv import load_dotenv

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.utils import (
    gather_bounded,
    get_gramps_id_from_handle,
    html_to_markdown,
    normalize_obj_class,
)

# Load environment variables from .env file
load_dotenv()


class TestHTMLToMarkdown:
    """Test HTML to Markdown conversion utility."""

    def test_basic_html_conversion(self):
        """Test basic HTML elements conversion."""
        html = "<h1>Title</h1><p>This is a paragraph.</p>"
        expected = "# Title\n\nThis is a paragraph."
        assert html_to_markdown(html).strip() == expected


class TestNormalizeObjClass:
    """Test normalize_obj_class utility function."""

    def test_numeric_code_person(self):
        """Test numeric code 0 maps to Person."""
        assert normalize_obj_class(0) == "Person"

    def test_numeric_code_place(self):
        """Test numeric code 5 maps to Place."""
        assert normalize_obj_class(5) == "Place"

    def test_string_digit(self):
        """Test string digit '5' maps to Place."""
        assert normalize_obj_class("5") == "Place"

    def test_unknown_numeric_code(self):
        """Test unknown numeric code returns Unknown(N)."""
        assert normalize_obj_class(99) == "Unknown(99)"

    def test_string_passthrough(self):
        """Test string class names pass through unchanged."""
        assert normalize_obj_class("Person") == "Person"

    def test_string_passthrough_lowercase(self):
        """Test lowercase string passes through unchanged."""
        assert normalize_obj_class("event") == "event"

    def test_all_known_codes(self):
        """Test all 10 known numeric codes resolve correctly."""
        expected = {
            0: "Person",
            1: "Family",
            2: "Source",
            3: "Event",
            4: "Media",
            5: "Place",
            6: "Repository",
            7: "Note",
            8: "Tag",
            9: "Citation",
        }
        for code, name in expected.items():
            assert normalize_obj_class(code) == name


class TestGetGrampsIdFromHandle:
    """Test get_gramps_id_from_handle utility function."""

    @pytest.mark.asyncio
    async def test_unknown_object_type_returns_handle(self):
        """Test that unknown object types return the original handle."""

        settings = get_settings()
        client = GrampsWebAPIClient()

        try:
            result = await get_gramps_id_from_handle(
                client, "unknown_type", "test_handle", settings.gramps_tree_id
            )

            # Should return the original handle for unknown types
            assert result == "test_handle"

        finally:
            await client.close()


class TestGatherBounded:
    """Test the bounded-concurrency gather helper."""

    @pytest.mark.asyncio
    async def test_preserves_input_order(self):
        """Results come back in input order regardless of completion order."""

        async def make(value: int) -> int:
            # Later-created coros sleep less, so they finish first.
            await asyncio.sleep(0.01 * (5 - value))
            return value

        result = await gather_bounded(3, [make(i) for i in range(5)])
        assert result == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_caps_in_flight_at_limit(self):
        """No more than `limit` awaitables run concurrently."""
        active = 0
        peak = 0

        async def task() -> None:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

        await gather_bounded(2, [task() for _ in range(6)])
        assert peak <= 2

    @pytest.mark.asyncio
    async def test_return_exceptions_true_yields_exception_in_place(self):
        """With return_exceptions, a failure is returned, not raised."""

        async def ok() -> str:
            return "ok"

        async def boom() -> str:
            raise ValueError("boom")

        result = await gather_bounded(2, [ok(), boom(), ok()], return_exceptions=True)
        assert result[0] == "ok"
        assert isinstance(result[1], ValueError)
        assert result[2] == "ok"

    @pytest.mark.asyncio
    async def test_return_exceptions_false_propagates(self):
        """Without return_exceptions, the first failure propagates."""

        async def boom() -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await gather_bounded(2, [boom()])
