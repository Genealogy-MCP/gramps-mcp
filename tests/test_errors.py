"""
Unit tests for error handling utilities and HTML/markdown conversion.

Tests McpToolError, raise_tool_error, and html_to_markdown edge cases.
"""

import pytest

from src.gramps_mcp.auth import GrampsAuthError
from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.tools._errors import (
    McpToolError,
    describe_auth_error,
    raise_tool_error,
)
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

    def test_auth_error_gets_actionable_message(self):
        """A login failure is described, not reported as unexpected."""
        original = GrampsAuthError(
            "Invalid username or password",
            status_code=403,
            error_type="invalid_credentials",
        )
        with pytest.raises(McpToolError) as exc_info:
            raise_tool_error(original, "person search")
        assert str(exc_info.value) == describe_auth_error(original)


class TestDescribeAuthError:
    """Map each login failure to an operator-actionable message (MCP-9)."""

    def test_invalid_credentials_names_the_settings(self):
        message = describe_auth_error(
            GrampsAuthError(
                "Invalid username or password",
                status_code=403,
                error_type="invalid_credentials",
            )
        )
        assert "GRAMPS_USERNAME" in message
        assert "GRAMPS_PASSWORD" in message
        assert "429" not in message

    def test_unconfirmed_account(self):
        message = describe_auth_error(
            GrampsAuthError(
                "Account not confirmed",
                status_code=403,
                error_type="account_unconfirmed",
            )
        )
        assert "not confirmed" in message

    def test_disabled_account(self):
        message = describe_auth_error(
            GrampsAuthError(
                "Account disabled", status_code=403, error_type="account_disabled"
            )
        )
        assert "disabled" in message

    def test_rate_limited_login_says_retry_shortly(self):
        message = describe_auth_error(GrampsAuthError("HTTP 429", status_code=429))
        assert "rate limited" in message
        assert "retry" in message.lower()

    def test_other_status_keeps_server_message(self):
        message = describe_auth_error(
            GrampsAuthError(
                "Local authentication is disabled. Please use OIDC authentication.",
                status_code=403,
            )
        )
        assert "HTTP 403" in message
        assert "OIDC" in message

    def test_transport_failure_keeps_detail(self):
        message = describe_auth_error(
            GrampsAuthError("Cannot connect to Gramps API: refused")
        )
        assert "Cannot connect to Gramps API: refused" in message


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
