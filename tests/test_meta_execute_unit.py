"""
Unit tests for meta_execute.py — identifier normalization and dispatch logic.

Tests _normalize_identifier() which maps the LLM-invented 'identifier' param
to the correct schema field (handle or gramps_id) based on value format and
schema introspection.
"""

from src.gramps_mcp.models.parameters.simple_params import (
    DeleteParams,
    SimpleGetParams,
)
from src.gramps_mcp.operations import DescendantsParams
from src.gramps_mcp.tools.meta_execute import _normalize_identifier

# ============================================================================
# _normalize_identifier
# ============================================================================


class TestNormalizeIdentifier:
    """Tests for centralized identifier normalization."""

    def test_identifier_classified_as_gramps_id(self) -> None:
        """Gramps ID pattern (letter + digits) maps to gramps_id."""
        params = {"type": "person", "identifier": "I0028"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result == {"type": "person", "gramps_id": "I0028"}
        assert "identifier" not in result

    def test_identifier_classified_as_handle(self) -> None:
        """Non-Gramps-ID value maps to handle."""
        params = {"type": "person", "identifier": "abc123longhandle"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result == {"type": "person", "handle": "abc123longhandle"}
        assert "identifier" not in result

    def test_identifier_skipped_when_handle_present(self) -> None:
        """Existing handle takes precedence over identifier."""
        params = {"type": "person", "handle": "real_handle", "identifier": "I0028"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result["handle"] == "real_handle"
        assert "identifier" not in result

    def test_identifier_skipped_when_gramps_id_present(self) -> None:
        """Existing gramps_id takes precedence over identifier."""
        params = {"type": "person", "gramps_id": "I0001", "identifier": "I0028"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result["gramps_id"] == "I0001"
        assert "identifier" not in result

    def test_identifier_maps_to_handle_when_schema_has_no_gramps_id(self) -> None:
        """DeleteParams only has handle — even Gramps ID pattern maps to handle."""
        params = {"type": "person", "identifier": "I0028"}
        result = _normalize_identifier(params, DeleteParams)
        assert result == {"type": "person", "handle": "I0028"}
        assert "identifier" not in result

    def test_no_identifier_no_change(self) -> None:
        """Params without identifier pass through unchanged."""
        params = {"type": "person", "handle": "abc123"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result == {"type": "person", "handle": "abc123"}

    def test_identifier_for_descendants_maps_to_gramps_id(self) -> None:
        """DescendantsParams has gramps_id only — identifier maps there."""
        params = {"identifier": "I0028"}
        result = _normalize_identifier(params, DescendantsParams)
        assert result == {"gramps_id": "I0028"}
        assert "identifier" not in result

    def test_identifier_non_gramps_id_maps_to_gramps_id_when_no_handle(self) -> None:
        """DescendantsParams has no handle — non-ID value still maps to gramps_id."""
        params = {"identifier": "some_handle_value"}
        result = _normalize_identifier(params, DescendantsParams)
        assert result == {"gramps_id": "some_handle_value"}

    def test_identifier_various_gramps_id_patterns(self) -> None:
        """Multiple Gramps ID prefixes are recognized."""
        for prefix in ("I", "F", "E", "P", "S", "C", "O", "R", "N"):
            params = {"identifier": f"{prefix}0001"}
            result = _normalize_identifier(params, SimpleGetParams)
            assert result.get("gramps_id") == f"{prefix}0001", (
                f"Failed for prefix {prefix}"
            )

    def test_identifier_empty_string_treated_as_handle(self) -> None:
        """Empty string is not a Gramps ID pattern — maps to handle."""
        params = {"type": "person", "identifier": ""}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result == {"type": "person", "handle": ""}

    def test_identifier_digits_only_treated_as_handle(self) -> None:
        """Pure digits (no letter prefix) are not Gramps IDs — map to handle."""
        params = {"type": "person", "identifier": "12345"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result == {"type": "person", "handle": "12345"}

    def test_original_dict_is_mutated(self) -> None:
        """Normalization mutates the input dict (not a copy)."""
        params = {"type": "person", "identifier": "I0028"}
        result = _normalize_identifier(params, SimpleGetParams)
        assert result is params
