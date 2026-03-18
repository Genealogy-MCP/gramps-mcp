"""Unit tests for family_handler and family_detail_handler formatting functions.

Tests format_family, format_family_detail with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.family_detail_handler import (
    format_family_detail,
)
from src.gramps_mcp.handlers.family_handler import (
    format_family,
)

TREE_ID = "test-tree"


class TestFormatFamily:
    """Test format_family handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_family(client, TREE_ID, "")
        assert "No handle provided" in result

    @pytest.mark.asyncio
    async def test_family_not_found(self):
        client = _mock_client({"GET_FAMILY": None})
        result = await format_family(client, TREE_ID, "handle123")
        assert "Family not found" in result

    @pytest.mark.asyncio
    async def test_family_basic(self):
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0001",
                    "father_handle": "",
                    "mother_handle": "",
                    "event_ref_list": [],
                    "child_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {"events": []},
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert "F0001" in result

    @pytest.mark.asyncio
    async def test_family_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_family(client, TREE_ID, "handle123")
        assert "Error formatting family" in result


class TestFormatFamilyExtended:
    """Test format_family with marriage/divorce, children, media, notes, URLs."""

    @pytest.mark.asyncio
    async def test_family_with_parents_and_marriage(self):
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0001",
                    "father_handle": "fh",
                    "mother_handle": "mh",
                    "event_ref_list": [{"ref": "evt1"}],
                    "child_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "father": {
                            "gramps_id": "I0001",
                            "gender": 1,
                            "primary_name": {
                                "first_name": "John",
                                "surname_list": [{"surname": "Smith"}],
                            },
                        },
                        "mother": {
                            "gramps_id": "I0002",
                            "gender": 0,
                            "primary_name": {
                                "first_name": "Mary",
                                "surname_list": [{"surname": "Jones"}],
                            },
                        },
                        "events": [
                            {
                                "type": "Marriage",
                                "date": {"dateval": [10, 6, 1880, False]},
                                "place": "",
                            }
                        ],
                    },
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert "Father: John Smith (M) - I0001" in result
        assert "Mother: Mary Jones (F) - I0002" in result
        assert "Married:" in result
        assert "1880" in result

    @pytest.mark.asyncio
    async def test_family_with_divorce(self):
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0002",
                    "event_ref_list": [{"ref": "evt1"}],
                    "child_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [
                            {
                                "type": "Divorce",
                                "date": {"dateval": [0, 0, 1895, False]},
                                "place": "place_h",
                            }
                        ],
                    },
                },
                "GET_PLACE": {
                    "title": "New York",
                    "name": {},
                    "placeref_list": [],
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert "Divorced:" in result
        assert "1895" in result

    @pytest.mark.asyncio
    async def test_family_with_children(self):
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0003",
                    "event_ref_list": [],
                    "child_ref_list": [{"ref": "c1"}, {"ref": "c2"}],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [],
                        "children": [
                            {
                                "gramps_id": "I0010",
                                "gender": 1,
                                "primary_name": {
                                    "first_name": "James",
                                    "surname_list": [{"surname": "Smith"}],
                                },
                            },
                            {
                                "gramps_id": "I0011",
                                "gender": 0,
                                "primary_name": {
                                    "first_name": "Alice",
                                    "surname_list": [{"surname": "Smith"}],
                                },
                            },
                        ],
                    },
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert "Children:" in result
        assert "James Smith (M) - I0010" in result
        assert "Alice Smith (F) - I0011" in result

    @pytest.mark.asyncio
    async def test_family_with_events_media_notes_urls(self):
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0004",
                    "event_ref_list": [{"ref": "e1", "role": "Family"}],
                    "child_ref_list": [],
                    "media_list": [{"ref": "m1"}],
                    "note_list": ["n1"],
                    "urls": [{"path": "https://family.org", "desc": "Family site"}],
                    "extended": {
                        "events": [{"type": "Census", "gramps_id": "E0020"}],
                        "media": [{"gramps_id": "O0010"}],
                        "notes": [{"gramps_id": "N0010"}],
                    },
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert "Events:" in result
        assert "Census, Family (E0020)" in result
        assert "Attached media: O0010" in result
        assert "Attached notes: N0010" in result
        assert "https://family.org - Family site" in result

    @pytest.mark.asyncio
    async def test_family_no_parents(self):
        """Family with no father/mother shows just gramps_id line."""
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0005",
                    "event_ref_list": [],
                    "child_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {"events": []},
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert result.startswith("F0005 - [handle123]")

    @pytest.mark.asyncio
    async def test_family_marriage_with_place(self):
        """Marriage event with a place shows place after date."""
        client = _mock_client(
            {
                "GET_FAMILY": {
                    "gramps_id": "F0006",
                    "event_ref_list": [{"ref": "e1"}],
                    "child_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "urls": [],
                    "extended": {
                        "events": [
                            {
                                "type": "Marriage",
                                "date": {"dateval": [5, 7, 1900, False]},
                                "place": "place_h",
                            }
                        ],
                    },
                },
                "GET_PLACE": {
                    "title": "Springfield",
                    "name": {},
                    "placeref_list": [],
                },
            }
        )
        result = await format_family(client, TREE_ID, "handle123")
        assert "Married:" in result
        assert "Springfield" in result


class TestFormatFamilyDetail:
    """Test format_family_detail handler."""

    @pytest.mark.asyncio
    async def test_family_detail_minimal(self):
        """Test family detail with no parents, children, or events."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "event_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                }
            if name == "GET_FAMILY_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_family_detail(client, TREE_ID, "handle123")
        assert "FAMILY DETAILS" in result
        assert "F0001" in result

    @pytest.mark.asyncio
    async def test_family_detail_with_parents(self):
        """Test family detail with father and mother."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "event_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "extended": {
                        "father": {
                            "handle": "father_h",
                            "gramps_id": "I0001",
                            "gender": 1,
                            "primary_name": {
                                "first_name": "John",
                                "surname_list": [{"surname": "Smith"}],
                            },
                        },
                        "mother": {
                            "handle": "mother_h",
                            "gramps_id": "I0002",
                            "gender": 0,
                            "primary_name": {
                                "first_name": "Mary",
                                "surname_list": [{"surname": "Jones"}],
                            },
                        },
                    },
                }
            if name == "GET_FAMILY_TIMELINE":
                return []
            if name == "GET_PERSON":
                return {
                    "birth_ref_index": -1,
                    "death_ref_index": -1,
                    "extended": {"events": []},
                }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_family_detail(client, TREE_ID, "handle123")
        assert "Father: John Smith" in result
        assert "Mother: Mary Jones" in result


class TestFormatFamilyDetailExtended:
    """Test format_family_detail with children, timeline, media, notes."""

    @pytest.mark.asyncio
    async def test_family_detail_with_children_and_dates(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "event_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "extended": {
                        "father": {
                            "handle": "fh",
                            "gramps_id": "I0001",
                            "gender": 1,
                            "primary_name": {
                                "first_name": "John",
                                "surname_list": [{"surname": "Smith"}],
                            },
                        },
                        "mother": {
                            "handle": "mh",
                            "gramps_id": "I0002",
                            "gender": 0,
                            "primary_name": {
                                "first_name": "Mary",
                                "surname_list": [{"surname": "Jones"}],
                            },
                        },
                        "children": [
                            {
                                "handle": "ch",
                                "gramps_id": "I0010",
                                "gender": 1,
                                "primary_name": {
                                    "first_name": "James",
                                    "surname_list": [{"surname": "Smith"}],
                                },
                            }
                        ],
                    },
                }
            if name == "GET_FAMILY_TIMELINE":
                return []
            if name == "GET_PERSON":
                return {
                    "birth_ref_index": 0,
                    "death_ref_index": -1,
                    "extended": {
                        "events": [
                            {"date": {"dateval": [0, 0, 1850, False]}, "place": ""}
                        ]
                    },
                }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_family_detail(client, TREE_ID, "fam_h")
        assert "CHILDREN:" in result
        assert "James Smith" in result
        assert "1850" in result

    @pytest.mark.asyncio
    async def test_family_detail_with_marriage_event(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "event_ref_list": [{"ref": "evt_h"}],
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                }
            if name == "GET_FAMILY_TIMELINE":
                return []
            if name == "GET_EVENT":
                return {
                    "type": "Marriage",
                    "date": {"dateval": [15, 6, 1880, False]},
                    "place": "",
                }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_family_detail(client, TREE_ID, "fam_h")
        assert "Married:" in result
        assert "1880" in result

    @pytest.mark.asyncio
    async def test_family_detail_with_timeline(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "event_ref_list": [],
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                }
            if name == "GET_FAMILY_TIMELINE":
                return [
                    {
                        "type": "Birth",
                        "gramps_id": "E0001",
                        "role": "Primary",
                        "handle": "evt_h",
                        "place": {"display_name": "Springfield"},
                        "person": {
                            "name_given": "James",
                            "name_surname": "Smith",
                            "gramps_id": "I0010",
                        },
                    }
                ]
            if name == "GET_EVENT":
                return {
                    "date": {"dateval": [1, 3, 1885, False]},
                    "extended": {
                        "citations": [{"gramps_id": "C0010"}],
                    },
                }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_family_detail(client, TREE_ID, "fam_h")
        assert "TIMELINE:" in result
        assert "Birth" in result
        assert "(Springfield)" in result
        assert "James Smith" in result
        assert "Citations: C0010" in result

    @pytest.mark.asyncio
    async def test_family_detail_with_media_and_notes(self):
        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name
            if name == "GET_FAMILY":
                return {
                    "gramps_id": "F0001",
                    "event_ref_list": [],
                    "media_list": [{"ref": "m1"}],
                    "note_list": ["n1"],
                    "extended": {
                        "media": [{"desc": "Wedding photo", "gramps_id": "O0001"}],
                        "notes": [
                            {
                                "type": "General",
                                "gramps_id": "N0001",
                                "text": {"string": "Family note content"},
                            }
                        ],
                    },
                }
            if name == "GET_FAMILY_TIMELINE":
                return []
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_family_detail(client, TREE_ID, "fam_h")
        assert "Wedding photo (O0001)" in result
        assert "General: Family note content (N0001)" in result
