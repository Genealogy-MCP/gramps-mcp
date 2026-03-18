"""Unit tests for date_handler formatting functions.

Tests format_date with various Gramps date objects (pure function, no mock needed).
"""

from src.gramps_mcp.handlers.date_handler import format_date


class TestFormatDate:
    """Test format_date with various Gramps date objects."""

    def test_empty_date(self):
        assert format_date({}) == "date unknown"

    def test_none_date(self):
        assert format_date(None) == "date unknown"

    def test_string_date(self):
        assert format_date({"string": "25 Dec 1900"}) == "25 Dec 1900"

    def test_full_dateval(self):
        result = format_date({"dateval": [15, 6, 1878, False]})
        assert "15" in result
        assert "June" in result
        assert "1878" in result

    def test_month_year_only(self):
        result = format_date({"dateval": [0, 3, 1900, False]})
        assert "March" in result
        assert "1900" in result

    def test_year_only(self):
        result = format_date({"dateval": [0, 0, 1850, False]})
        assert result == "1850"

    def test_zero_year(self):
        assert format_date({"dateval": [1, 1, 0, False]}) == "date unknown"

    def test_negative_year(self):
        assert format_date({"dateval": [1, 1, -5, False]}) == "date unknown"

    def test_short_dateval(self):
        assert format_date({"dateval": [1, 2]}) == "date unknown"

    def test_modifier_before(self):
        result = format_date({"dateval": [0, 0, 1900, False], "modifier": 1})
        assert result.startswith("before ")

    def test_modifier_after(self):
        result = format_date({"dateval": [0, 0, 1900, False], "modifier": 2})
        assert result.startswith("after ")

    def test_modifier_about(self):
        result = format_date({"dateval": [0, 0, 1900, False], "modifier": 3})
        assert result.startswith("about ")

    def test_quality_estimated(self):
        result = format_date({"dateval": [0, 0, 1900, False], "quality": 1})
        assert "(estimated)" in result

    def test_quality_calculated(self):
        result = format_date({"dateval": [0, 0, 1900, False], "quality": 2})
        assert "(calculated)" in result

    def test_invalid_date_values(self):
        # month=13 triggers ValueError in datetime
        result = format_date({"dateval": [1, 13, 1900, False]})
        assert result == "1900"

    def test_modifier_range(self):
        """Modifier 4 (range) with 8-element dateval uses 'between' prefix."""
        result = format_date(
            {
                "dateval": [1, 1, 1850, False, 31, 12, 1860, False],
                "modifier": 4,
            }
        )
        assert result.startswith("between ")
        assert "1850" in result

    def test_modifier_span(self):
        """Modifier 5 (span) with 8-element dateval uses 'from' prefix."""
        result = format_date(
            {
                "dateval": [1, 6, 1900, False, 30, 6, 1910, False],
                "modifier": 5,
            }
        )
        assert result.startswith("from ")
        assert "1900" in result

    def test_modifier_from(self):
        """Modifier 7 uses 'from' prefix."""
        result = format_date({"dateval": [0, 0, 1800, False], "modifier": 7})
        assert result.startswith("from ")
        assert "1800" in result

    def test_modifier_to(self):
        """Modifier 8 uses 'to' prefix."""
        result = format_date({"dateval": [0, 0, 1900, False], "modifier": 8})
        assert result.startswith("to ")
        assert "1900" in result

    def test_combined_modifier_and_quality(self):
        """Modifier + quality combine correctly."""
        result = format_date(
            {"dateval": [0, 0, 1850, False], "modifier": 3, "quality": 1}
        )
        assert result == "about 1850 (estimated)"
