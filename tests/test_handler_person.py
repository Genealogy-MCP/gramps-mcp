"""Unit tests for person_handler and person_detail_handler formatting functions.

Tests format_person, format_person_detail, _extract_person_name, and
_get_gender_letter with mock API responses (no network calls).
Also tests shared helper functions (_extract_person_name, _get_gender_letter)
across all handlers that define them.
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.family_detail_handler import (
    _extract_person_name as family_detail_extract_name,
)
from src.gramps_mcp.handlers.family_detail_handler import (
    _get_gender_letter as family_detail_gender,
)
from src.gramps_mcp.handlers.family_handler import (
    _extract_person_name as family_extract_name,
)
from src.gramps_mcp.handlers.family_handler import (
    _get_gender_letter as family_gender,
)
from src.gramps_mcp.handlers.person_detail_handler import (
    _extract_person_name as person_detail_extract_name,
)
from src.gramps_mcp.handlers.person_detail_handler import (
    _get_gender_letter as person_detail_gender,
)
from src.gramps_mcp.handlers.person_detail_handler import (
    format_person_detail,
)
from src.gramps_mcp.handlers.person_handler import format_person

TREE_ID = "test-tree"


class TestExtractPersonName:
    """Test _extract_person_name across all handlers that define it."""

    def test_full_name(self):
        data = {
            "primary_name": {
                "first_name": "John",
                "surname_list": [{"surname": "Smith"}],
            }
        }
        assert family_detail_extract_name(data) == "John Smith"
        assert person_detail_extract_name(data) == "John Smith"

    def test_first_name_only(self):
        data = {"primary_name": {"first_name": "Mary", "surname_list": []}}
        assert family_detail_extract_name(data) == "Mary"

    def test_no_primary_name(self):
        assert family_detail_extract_name({}) == "Unknown"
        assert person_detail_extract_name({}) == "Unknown"

    def test_empty_primary_name(self):
        data = {"primary_name": {}}
        # Empty dict is falsy in Python, so falls through to "Unknown"
        result = family_detail_extract_name(data)
        assert result == "Unknown"

    def test_family_handler_empty_name_returns_empty(self):
        data = {"primary_name": {"first_name": "", "surname_list": []}}
        assert family_extract_name(data) == ""

    def test_family_handler_no_primary_name(self):
        assert family_extract_name({}) == ""


class TestGetGenderLetter:
    """Test _get_gender_letter across handlers."""

    def test_female(self):
        assert family_detail_gender(0) == "F"
        assert family_gender(0) == "F"
        assert person_detail_gender(0) == "F"

    def test_male(self):
        assert family_detail_gender(1) == "M"

    def test_unknown(self):
        assert family_detail_gender(2) == "U"

    def test_invalid(self):
        assert family_detail_gender(99) == "U"


class TestFormatPerson:
    """Test format_person handler."""

    @pytest.mark.asyncio
    async def test_person_basic(self):
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {"events": [], "families": [], "parent_families": []},
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "John Smith" in result
        assert "(M)" in result
        assert "I0001" in result

    @pytest.mark.asyncio
    async def test_person_not_found(self):
        client = _mock_client({"GET_PERSON": None})
        result = await format_person(client, TREE_ID, "handle123")
        assert "Unknown Person" in result

    @pytest.mark.asyncio
    async def test_person_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_person(client, TREE_ID, "handle123")
        assert "Error formatting person" in result


class TestFormatPersonExtended:
    """Test format_person with birth/death events, families, media, notes, URLs."""

    @pytest.mark.asyncio
    async def test_person_with_birth_and_death(self):
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": 0,
                    "death_ref_index": 1,
                    "event_ref_list": [
                        {"ref": "birth_h", "role": "Primary"},
                        {"ref": "death_h", "role": "Primary"},
                    ],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [
                            {
                                "date": {"dateval": [1, 5, 1850, False]},
                                "place": "place_h",
                            },
                            {
                                "date": {"dateval": [15, 3, 1920, False]},
                                "place": "",
                            },
                        ],
                        "families": [],
                        "parent_families": [],
                    },
                },
                "GET_PLACE": {
                    "title": "Boston, MA",
                    "name": {},
                    "placeref_list": [],
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Born:" in result
        assert "1850" in result
        assert "Died:" in result
        assert "1920" in result

    @pytest.mark.asyncio
    async def test_person_with_family_relationships(self):
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": ["fam1"],
                    "parent_family_list": ["fam2"],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [],
                        "families": [{"gramps_id": "F0001"}],
                        "parent_families": [{"gramps_id": "F0002"}],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Family member of:" in result
        assert "child (F0002)" in result
        assert "parent (F0001)" in result

    @pytest.mark.asyncio
    async def test_person_with_events_list(self):
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [
                        {"ref": "e1", "role": "Primary"},
                        {"ref": "e2", "role": "Witness"},
                    ],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [
                            {"type": "Birth", "gramps_id": "E0001"},
                            {"type": "Baptism", "gramps_id": "E0002"},
                        ],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Events:" in result
        assert "Birth, Primary (E0001)" in result
        assert "Baptism, Witness (E0002)" in result

    @pytest.mark.asyncio
    async def test_person_with_media_notes_urls(self):
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "Jane",
                        "surname_list": [{"surname": "Doe"}],
                    },
                    "gender": 0,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [{"ref": "m1"}],
                    "note_list": ["n1"],
                    "urls": [
                        {"path": "https://example.com", "desc": "Homepage"},
                        {"path": "https://other.com", "desc": ""},
                    ],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                        "media": [{"gramps_id": "O0001"}],
                        "notes": [{"gramps_id": "N0001"}],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Attached media: O0001" in result
        assert "Attached notes: N0001" in result
        assert "https://example.com - Homepage" in result
        assert "https://other.com\n" in result

    @pytest.mark.asyncio
    async def test_person_event_no_role(self):
        """Event ref without a role key."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": ["plain_ref"],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [{"type": "Census", "gramps_id": "E0010"}],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Census (E0010)" in result


class TestFormatPersonDetail:
    """Test format_person_detail handler."""

    @pytest.mark.asyncio
    async def test_person_detail_minimal(self):
        """Test person detail with minimal data."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "extended": {"events": []},
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "handle123")
        assert "PERSON DETAILS" in result
        assert "John Smith" in result
        assert "(M)" in result
        assert "I0001" in result


class TestFormatPersonDetailExtended:
    """Test format_person_detail with relations, timeline, media, notes."""

    @pytest.mark.asyncio
    async def test_person_detail_with_birth_death(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 0,
                    "primary_name": {
                        "first_name": "Jane",
                        "surname_list": [{"surname": "Doe"}],
                    },
                    "birth_ref_index": 0,
                    "death_ref_index": 1,
                    "event_ref_list": [{"ref": "b1"}, {"ref": "d1"}],
                    "parent_family_list": [],
                    "family_list": [],
                    "extended": {
                        "events": [
                            {"date": {"dateval": [1, 1, 1800, False]}, "place": ""},
                            {"date": {"dateval": [1, 1, 1870, False]}, "place": ""},
                        ],
                    },
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "Born:" in result
        assert "1800" in result
        assert "Died:" in result
        assert "1870" in result

    @pytest.mark.asyncio
    async def test_person_detail_with_parents_and_siblings(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON" and handle == "h1":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": ["fam_h"],
                    "family_list": [],
                    "extended": {"events": []},
                }
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "extended": {
                        "father": {
                            "handle": "dad_h",
                            "gramps_id": "I0010",
                            "primary_name": {
                                "first_name": "Robert",
                                "surname_list": [{"surname": "Smith"}],
                            },
                        },
                        "mother": {
                            "handle": "mom_h",
                            "gramps_id": "I0011",
                            "primary_name": {
                                "first_name": "Susan",
                                "surname_list": [{"surname": "Brown"}],
                            },
                        },
                        "children": [
                            {"gramps_id": "I0001"},
                            {
                                "handle": "sib_h",
                                "gramps_id": "I0012",
                                "primary_name": {
                                    "first_name": "Alice",
                                    "surname_list": [{"surname": "Smith"}],
                                },
                            },
                        ],
                    },
                }
            if name == "GET_PERSON":
                return {
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "extended": {"events": []},
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "Robert Smith" in result
        assert "Susan Brown" in result
        assert "Siblings:" in result
        assert "Alice Smith" in result

    @pytest.mark.asyncio
    async def test_person_detail_with_spouse_and_children(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON" and handle == "h1":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": ["fam_h"],
                    "extended": {"events": []},
                }
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "extended": {
                        "father": {"gramps_id": "I0001"},
                        "mother": {
                            "handle": "spouse_h",
                            "gramps_id": "I0020",
                            "primary_name": {
                                "first_name": "Mary",
                                "surname_list": [{"surname": "Jones"}],
                            },
                        },
                        "children": [
                            {
                                "handle": "child_h",
                                "gramps_id": "I0030",
                                "primary_name": {
                                    "first_name": "James",
                                    "surname_list": [{"surname": "Smith"}],
                                },
                            }
                        ],
                    },
                }
            if name == "GET_PERSON":
                return {
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "extended": {"events": []},
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "Spouse:" in result
        assert "Mary Jones" in result
        assert "Children:" in result
        assert "James Smith" in result

    @pytest.mark.asyncio
    async def test_person_detail_with_timeline(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "extended": {"events": [], "media": [], "notes": []},
                }
            if name == "GET_PERSON_TIMELINE":
                return [
                    {
                        "type": "Birth",
                        "gramps_id": "E0001",
                        "role": "Primary",
                        "handle": "evt_h",
                        "place": {"display_name": "Boston"},
                        "person": {"relationship": "self"},
                    }
                ]
            if name == "GET_EVENT":
                return {
                    "date": {"dateval": [1, 5, 1850, False]},
                    "extended": {
                        "citations": [{"gramps_id": "C0001"}],
                    },
                }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "TIMELINE:" in result
        assert "Birth" in result
        assert "(Boston)" in result
        assert "Citations: C0001" in result

    @pytest.mark.asyncio
    async def test_person_detail_timeline_other_person(self):
        """Timeline event for another person (not self)."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "extended": {"events": [], "media": [], "notes": []},
                }
            if name == "GET_PERSON_TIMELINE":
                return [
                    {
                        "type": "Marriage",
                        "gramps_id": "E0050",
                        "role": "Bride",
                        "handle": "evt_h",
                        "place": {},
                        "person": {
                            "relationship": "spouse",
                            "name_given": "Mary",
                            "name_surname": "Jones",
                            "gramps_id": "I0020",
                        },
                    }
                ]
            if name == "GET_EVENT":
                return {
                    "date": {"dateval": [0, 0, 1880, False]},
                    "extended": {},
                }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "Mary Jones" in result
        assert "Bride" in result

    @pytest.mark.asyncio
    async def test_person_detail_with_media_and_notes(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "extended": {
                        "events": [],
                        "media": [{"desc": "Photo", "gramps_id": "O0001"}],
                        "notes": [
                            {
                                "type": "Research",
                                "gramps_id": "N0001",
                                "text": {"string": "Very long note " + "x" * 60},
                            }
                        ],
                    },
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "Photo (O0001)" in result
        assert "Research:" in result
        assert "..." in result


class TestFormatPersonPrimaryNameCitations:
    """Test primary name citation display in format_person."""

    @pytest.mark.asyncio
    async def test_primary_name_with_citations(self):
        """Primary name citations resolved from extended.citations appear on name line."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                        "citation_list": ["cit_h1", "cit_h2"],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                        "citations": [
                            {"handle": "cit_h1", "gramps_id": "C0042"},
                            {"handle": "cit_h2", "gramps_id": "C0043"},
                        ],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "[C0042, C0043]" in result

    @pytest.mark.asyncio
    async def test_primary_name_no_citations_no_brackets(self):
        """No citation handles on primary name means no brackets on name line."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        first_line = result.split("\n")[0]
        # Should end with [handle123] and no extra citation brackets
        assert first_line.endswith("[handle123]")


class TestFormatPersonAlternateNames:
    """Test alternate name display in format_person."""

    @pytest.mark.asyncio
    async def test_single_alternate_name_dict_type(self):
        """Alternate name with dict-format type field."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "alternate_names": [
                        {
                            "first_name": "Pascual",
                            "surname_list": [{"surname": "Civitilli"}],
                            "type": {
                                "_class": "NameType",
                                "string": "Also Known As",
                            },
                        }
                    ],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Alternate names:\n" in result
        assert "  - Also Known As: Pascual Civitilli\n" in result

    @pytest.mark.asyncio
    async def test_alternate_name_with_citations(self):
        """Alternate name citations resolved via handle->gramps_id map."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "alternate_names": [
                        {
                            "first_name": "Giovanni",
                            "surname_list": [{"surname": "Rossi"}],
                            "type": {
                                "_class": "NameType",
                                "string": "Birth Name",
                            },
                            "citation_list": ["cit_h1"],
                        }
                    ],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                        "citations": [
                            {"handle": "cit_h1", "gramps_id": "C0184"},
                        ],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "  - Birth Name: Giovanni Rossi [C0184]\n" in result

    @pytest.mark.asyncio
    async def test_multiple_alternate_names(self):
        """Multiple alternate names each on their own line."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "Maria",
                        "surname_list": [{"surname": "Garcia"}],
                    },
                    "gender": 0,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "alternate_names": [
                        {
                            "first_name": "Mary",
                            "surname_list": [{"surname": "Garcia"}],
                            "type": {"_class": "NameType", "string": "Also Known As"},
                        },
                        {
                            "first_name": "Maria",
                            "surname_list": [{"surname": "Lopez"}],
                            "type": {"_class": "NameType", "string": "Married Name"},
                        },
                    ],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "  - Also Known As: Mary Garcia\n" in result
        assert "  - Married Name: Maria Lopez\n" in result

    @pytest.mark.asyncio
    async def test_no_alternate_names_absent(self):
        """No alternate names -> 'Alternate names:' absent from output."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "Alternate names:" not in result

    @pytest.mark.asyncio
    async def test_type_as_plain_string(self):
        """API 3.x may return type as plain string, not dict."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "alternate_names": [
                        {
                            "first_name": "Jon",
                            "surname_list": [{"surname": "Smith"}],
                            "type": "Also Known As",
                        }
                    ],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "  - Also Known As: Jon Smith\n" in result

    @pytest.mark.asyncio
    async def test_missing_type_field(self):
        """Missing type field -> name shown without prefix."""
        client = _mock_client(
            {
                "GET_PERSON": {
                    "gramps_id": "I0001",
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "gender": 1,
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "event_ref_list": [],
                    "family_list": [],
                    "parent_family_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "alternate_names": [
                        {
                            "first_name": "Johann",
                            "surname_list": [{"surname": "Schmidt"}],
                        }
                    ],
                    "extended": {
                        "events": [],
                        "families": [],
                        "parent_families": [],
                    },
                },
            }
        )
        result = await format_person(client, TREE_ID, "handle123")
        assert "  - Johann Schmidt\n" in result


class TestFormatPersonDetailAlternateNames:
    """Test alternate name display in format_person_detail."""

    @pytest.mark.asyncio
    async def test_detail_single_alternate_name(self):
        """Alternate name appears in detail output."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "alternate_names": [
                        {
                            "first_name": "Jon",
                            "surname_list": [{"surname": "Smyth"}],
                            "type": {
                                "_class": "NameType",
                                "string": "Also Known As",
                            },
                        }
                    ],
                    "extended": {"events": [], "media": [], "notes": []},
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "Alternate names:\n" in result
        assert "  - Also Known As: Jon Smyth\n" in result

    @pytest.mark.asyncio
    async def test_detail_alternate_name_with_citations(self):
        """Alternate name citations resolved in detail view."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "alternate_names": [
                        {
                            "first_name": "Giovanni",
                            "surname_list": [{"surname": "Fabbro"}],
                            "type": {
                                "_class": "NameType",
                                "string": "Birth Name",
                            },
                            "citation_list": ["cit_h1"],
                        }
                    ],
                    "extended": {
                        "events": [],
                        "media": [],
                        "notes": [],
                        "citations": [
                            {"handle": "cit_h1", "gramps_id": "C0099"},
                        ],
                    },
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        assert "  - Birth Name: Giovanni Fabbro [C0099]\n" in result

    @pytest.mark.asyncio
    async def test_detail_primary_name_citations_on_header(self):
        """Primary name citations shown on header line in detail view."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_PERSON":
                return {
                    "gramps_id": "I0001",
                    "gender": 1,
                    "primary_name": {
                        "first_name": "John",
                        "surname_list": [{"surname": "Smith"}],
                        "citation_list": ["cit_h1"],
                    },
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "parent_family_list": [],
                    "family_list": [],
                    "extended": {
                        "events": [],
                        "media": [],
                        "notes": [],
                        "citations": [
                            {"handle": "cit_h1", "gramps_id": "C0055"},
                        ],
                    },
                }
            if name == "GET_PERSON_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_person_detail(client, TREE_ID, "h1")
        first_data_line = result.split("\n")[1]
        assert "[C0055]" in first_data_line
