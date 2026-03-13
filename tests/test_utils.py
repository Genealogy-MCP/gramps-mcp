"""
Tests for utility functions.
"""

import pytest
from dotenv import load_dotenv

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.config import get_settings
from src.gramps_mcp.utils import (
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
