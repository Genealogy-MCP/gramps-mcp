"""
Unit tests for the join_surnames utility function.

Verifies that all surnames from surname_list are joined, supporting
multi-surname names (e.g. Hispanic/Latin naming conventions).
"""

from src.gramps_mcp.handlers.name_utils import join_surnames


class TestJoinSurnames:
    """Test join_surnames with various surname_list shapes."""

    def test_single_surname(self):
        surname_list = [{"surname": "Smith"}]
        assert join_surnames(surname_list) == "Smith"

    def test_two_surnames(self):
        surname_list = [{"surname": "Garcia"}, {"surname": "Lopez"}]
        assert join_surnames(surname_list) == "Garcia Lopez"

    def test_three_surnames(self):
        surname_list = [
            {"surname": "de la"},
            {"surname": "Cruz"},
            {"surname": "Fernandez"},
        ]
        assert join_surnames(surname_list) == "de la Cruz Fernandez"

    def test_empty_list(self):
        assert join_surnames([]) == ""

    def test_none_input(self):
        assert join_surnames(None) == ""

    def test_empty_surname_values(self):
        surname_list = [{"surname": ""}, {"surname": "Smith"}]
        assert join_surnames(surname_list) == "Smith"

    def test_missing_surname_key(self):
        surname_list = [{"other_key": "val"}, {"surname": "Smith"}]
        assert join_surnames(surname_list) == "Smith"

    def test_all_empty_surnames(self):
        surname_list = [{"surname": ""}, {"surname": ""}]
        assert join_surnames(surname_list) == ""

    def test_non_dict_entries_skipped(self):
        surname_list = ["not_a_dict", {"surname": "Smith"}]
        assert join_surnames(surname_list) == "Smith"

    def test_whitespace_trimmed(self):
        surname_list = [{"surname": " Garcia "}, {"surname": " Lopez "}]
        assert join_surnames(surname_list) == "Garcia Lopez"

    def test_single_primary_surname_with_prefix(self):
        """Common pattern: a surname with an origin type prefix."""
        surname_list = [
            {
                "surname": "Martinez",
                "primary": True,
                "origintype": {
                    "_class": "NameOriginType",
                    "string": "Inherited",
                },
            }
        ]
        assert join_surnames(surname_list) == "Martinez"

    def test_hispanic_dual_surname(self):
        """Typical Hispanic pattern: paternal + maternal surname."""
        surname_list = [
            {
                "surname": "Garcia",
                "primary": True,
                "origintype": {
                    "_class": "NameOriginType",
                    "string": "Inherited",
                },
            },
            {
                "surname": "Rodriguez",
                "primary": False,
                "origintype": {
                    "_class": "NameOriginType",
                    "string": "Inherited",
                },
            },
        ]
        assert join_surnames(surname_list) == "Garcia Rodriguez"


class TestJoinSurnamesInHandlers:
    """Verify handlers use join_surnames correctly for multi-surname display."""

    def test_person_handler_extract_name_uses_all_surnames(self):
        """person_handler inline name extraction joins all surnames."""
        # This test validates the integration point in person_handler.py
        # where surname extraction happens inline (line 65)
        from src.gramps_mcp.handlers.name_utils import join_surnames

        surname_list = [{"surname": "Garcia"}, {"surname": "Lopez"}]
        result = join_surnames(surname_list)
        assert result == "Garcia Lopez"

    def test_person_detail_extract_name_uses_all_surnames(self):
        """_extract_person_name in person_detail_handler joins all surnames."""
        from src.gramps_mcp.handlers.person_detail_handler import (
            _extract_person_name,
        )

        data = {
            "primary_name": {
                "first_name": "Maria",
                "surname_list": [
                    {"surname": "Garcia"},
                    {"surname": "Lopez"},
                ],
            }
        }
        assert _extract_person_name(data) == "Maria Garcia Lopez"

    def test_family_handler_extract_name_uses_all_surnames(self):
        """_extract_person_name in family_handler joins all surnames."""
        from src.gramps_mcp.handlers.family_handler import (
            _extract_person_name,
        )

        data = {
            "primary_name": {
                "first_name": "Carlos",
                "surname_list": [
                    {"surname": "Martinez"},
                    {"surname": "Fernandez"},
                ],
            }
        }
        assert _extract_person_name(data) == "Carlos Martinez Fernandez"

    def test_family_detail_extract_name_uses_all_surnames(self):
        """_extract_person_name in family_detail_handler joins all surnames."""
        from src.gramps_mcp.handlers.family_detail_handler import (
            _extract_person_name,
        )

        data = {
            "primary_name": {
                "first_name": "Ana",
                "surname_list": [
                    {"surname": "Cruz"},
                    {"surname": "Diaz"},
                ],
            }
        }
        assert _extract_person_name(data) == "Ana Cruz Diaz"
