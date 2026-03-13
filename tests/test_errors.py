"""
Unit tests for error handling utilities and HTML/markdown conversion.

Tests McpToolError, raise_tool_error, and html_to_markdown edge cases.
"""

import pytest

from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.tools._errors import McpToolError, raise_tool_error
from src.gramps_mcp.utils import html_to_markdown


class TestMcpToolError:
    """Test McpToolError exception class."""

    def test_basic_error(self):
        error = McpToolError("something broke")
        assert str(error) == "something broke"

    def test_inherits_from_exception(self):
        assert issubclass(McpToolError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(McpToolError):
            raise McpToolError("test")


class TestRaiseToolError:
    """Test raise_tool_error utility."""

    def test_gramps_api_error(self):
        """GrampsAPIError messages are passed through directly."""
        original = GrampsAPIError("404: Person not found")
        with pytest.raises(McpToolError, match="404: Person not found"):
            raise_tool_error(original, "person lookup")

    def test_mcp_tool_error_passthrough(self):
        """McpToolError messages are passed through."""
        original = McpToolError("already formatted error")
        with pytest.raises(McpToolError, match="already formatted error"):
            raise_tool_error(original, "re-raise")

    def test_generic_exception(self):
        """Generic exceptions get wrapped with operation context."""
        original = ValueError("bad value")
        with pytest.raises(McpToolError, match="Unexpected error during save"):
            raise_tool_error(original, "save")

    def test_chained_exception(self):
        """Original exception is chained via `from`."""
        original = RuntimeError("root cause")
        with pytest.raises(McpToolError) as exc_info:
            raise_tool_error(original, "test")
        assert exc_info.value.__cause__ is original

    def test_return_type_is_noreturn(self):
        """Function always raises, never returns."""
        with pytest.raises(McpToolError):
            raise_tool_error(Exception("x"), "op")


class TestHtmlToMarkdown:
    """Test html_to_markdown utility edge cases."""

    def test_empty_string(self):
        assert html_to_markdown("") == ""

    def test_whitespace_only(self):
        assert html_to_markdown("   ") == ""

    def test_none_input(self):
        assert html_to_markdown(None) == ""

    def test_paragraph(self):
        result = html_to_markdown("<p>Hello world</p>")
        assert "Hello world" in result

    def test_heading(self):
        result = html_to_markdown("<h2>Title</h2>")
        assert "## Title" in result

    def test_bold(self):
        result = html_to_markdown("<b>important</b>")
        assert "**important**" in result

    def test_link(self):
        result = html_to_markdown('<a href="https://example.com">link</a>')
        assert "example.com" in result

    def test_list(self):
        result = html_to_markdown("<ul><li>item1</li><li>item2</li></ul>")
        assert "item1" in result
        assert "item2" in result

    def test_nested_html(self):
        result = html_to_markdown("<div><p>nested <em>content</em></p></div>")
        assert "nested" in result
        assert "content" in result
