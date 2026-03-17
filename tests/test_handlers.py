"""
Unit tests for handler formatting functions.

Tests handler output with mock API responses (no network calls).
Each handler formats Gramps API data into human-readable strings.
"""

from unittest.mock import AsyncMock

import pytest

from src.gramps_mcp.handlers.citation_handler import format_citation
from src.gramps_mcp.handlers.date_handler import format_date
from src.gramps_mcp.handlers.event_handler import format_event
from src.gramps_mcp.handlers.family_detail_handler import (
    _extract_person_name as family_detail_extract_name,
)
from src.gramps_mcp.handlers.family_detail_handler import (
    _get_gender_letter as family_detail_gender,
)
from src.gramps_mcp.handlers.family_detail_handler import (
    format_family_detail,
)
from src.gramps_mcp.handlers.family_handler import (
    _extract_person_name as family_extract_name,
)
from src.gramps_mcp.handlers.family_handler import (
    _get_gender_letter as family_gender,
)
from src.gramps_mcp.handlers.family_handler import (
    format_family,
)
from src.gramps_mcp.handlers.media_handler import format_media
from src.gramps_mcp.handlers.note_handler import format_note
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
from src.gramps_mcp.handlers.place_handler import format_place
from src.gramps_mcp.handlers.repository_handler import format_repository
from src.gramps_mcp.handlers.source_handler import format_source
from src.gramps_mcp.tools.analysis import _format_recent_changes

TREE_ID = "test-tree"


def _mock_client(responses):
    """Create a mock client returning predefined responses by API call name.

    Keys should be enum names like "GET_NOTE", "GET_SOURCE", etc.
    Values can be a dict (same response every time) or a list of dicts
    (returns each in sequence, repeating the last for extra calls).
    """
    client = AsyncMock()
    call_count = {}

    async def mock_api_call(api_call, tree_id=None, handle=None, params=None):
        key = api_call.name if hasattr(api_call, "name") else str(api_call)
        call_count.setdefault(key, 0)
        if key in responses:
            val = responses[key]
            if isinstance(val, list):
                idx = min(call_count[key], len(val) - 1)
                call_count[key] += 1
                return val[idx]
            return val
        return {}

    client.make_api_call = AsyncMock(side_effect=mock_api_call)
    return client


# ============================================================
# date_handler — pure function, no mock needed
# ============================================================


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


# ============================================================
# Helper functions (pure, shared across handlers)
# ============================================================


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


# ============================================================
# note_handler — async with mock client
# ============================================================


class TestFormatNote:
    """Test format_note handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        assert await format_note(client, TREE_ID, "") == ""

    @pytest.mark.asyncio
    async def test_note_not_found(self):
        client = _mock_client({"GET_NOTE": None})
        assert await format_note(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_note_with_content(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0001",
                    "type": "General",
                    "text": {"string": "This is a test note."},
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "General Note" in result
        assert "N0001" in result
        assert "This is a test note." in result

    @pytest.mark.asyncio
    async def test_note_truncation(self):
        long_text = "A" * 600
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0002",
                    "type": "Research",
                    "text": {"string": long_text},
                }
            }
        )
        result = await format_note(client, TREE_ID, "handle123")
        assert "..." in result
        assert len(result) < 600

    @pytest.mark.asyncio
    async def test_note_empty_text(self):
        client = _mock_client(
            {
                "GET_NOTE": {
                    "gramps_id": "N0003",
                    "type": "General",
                    "text": {"string": ""},
                }
            }
        )
        assert await format_note(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_note_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("API error"))
        assert await format_note(client, TREE_ID, "handle123") == ""


# ============================================================
# media_handler
# ============================================================


class TestFormatMedia:
    """Test format_media handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_media(client, TREE_ID, "")
        assert "No handle provided" in result

    @pytest.mark.asyncio
    async def test_media_not_found(self):
        client = _mock_client({"GET_MEDIA_ITEM": None})
        result = await format_media(client, TREE_ID, "handle123")
        assert "Media not found" in result

    @pytest.mark.asyncio
    async def test_media_with_details(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0001",
                    "desc": "Photo of John",
                    "mime": "image/jpeg",
                    "date": None,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "image/jpeg" in result
        assert "O0001" in result
        assert "Photo of John" in result

    @pytest.mark.asyncio
    async def test_media_with_date(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0002",
                    "desc": "Wedding photo",
                    "mime": "image/png",
                    "date": {"dateval": [15, 6, 1920, False]},
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "June" in result
        assert "1920" in result

    @pytest.mark.asyncio
    async def test_media_no_description(self):
        client = _mock_client(
            {
                "GET_MEDIA_ITEM": {
                    "gramps_id": "O0003",
                    "desc": "",
                    "mime": "",
                    "date": None,
                }
            }
        )
        result = await format_media(client, TREE_ID, "handle123")
        assert "No description" in result
        assert "unknown type" in result

    @pytest.mark.asyncio
    async def test_media_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("timeout"))
        result = await format_media(client, TREE_ID, "handle123")
        assert "Error formatting media" in result


# ============================================================
# source_handler
# ============================================================


class TestFormatSource:
    """Test format_source handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_source(client, TREE_ID, "")
        assert "Unknown Source" in result

    @pytest.mark.asyncio
    async def test_source_not_found(self):
        client = _mock_client({"GET_SOURCE": None})
        result = await format_source(client, TREE_ID, "handle123")
        assert "Source not found" in result

    @pytest.mark.asyncio
    async def test_source_basic(self):
        client = _mock_client(
            {
                "GET_SOURCE": {
                    "gramps_id": "S0001",
                    "title": "Marriage Register",
                    "author": "St. Mary's",
                    "pubinfo": "Original manuscript",
                    "note_list": [],
                    "reporef_list": [],
                    "media_list": [],
                }
            }
        )
        result = await format_source(client, TREE_ID, "handle123")
        assert "Marriage Register" in result
        assert "S0001" in result
        assert "St. Mary's" in result
        assert "Original manuscript" in result

    @pytest.mark.asyncio
    async def test_source_no_author(self):
        client = _mock_client(
            {
                "GET_SOURCE": {
                    "gramps_id": "S0002",
                    "title": "Census 1900",
                    "author": "",
                    "pubinfo": "",
                    "note_list": [],
                    "reporef_list": [],
                    "media_list": [],
                }
            }
        )
        result = await format_source(client, TREE_ID, "handle123")
        assert "Census 1900" in result
        # No second line since no author or pubinfo
        assert result.count("\n") >= 1

    @pytest.mark.asyncio
    async def test_source_with_repo(self):
        client = _mock_client(
            {
                "GET_SOURCE": {
                    "gramps_id": "S0003",
                    "title": "Church Records",
                    "author": "",
                    "pubinfo": "",
                    "note_list": [],
                    "reporef_list": [{"ref": "repo_handle_1"}],
                    "media_list": [],
                    "extended": {
                        "repositories": [
                            {"name": "National Archives", "gramps_id": "R0001"}
                        ],
                        "media": [],
                        "notes": [],
                    },
                },
            }
        )
        result = await format_source(client, TREE_ID, "handle123")
        assert "National Archives" in result
        assert "R0001" in result

    @pytest.mark.asyncio
    async def test_source_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("network error"))
        result = await format_source(client, TREE_ID, "handle123")
        assert "Error formatting source" in result


# ============================================================
# repository_handler
# ============================================================


class TestFormatRepository:
    """Test format_repository handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        assert await format_repository(client, TREE_ID, "") == ""

    @pytest.mark.asyncio
    async def test_repo_not_found(self):
        client = _mock_client({"GET_REPOSITORY": None})
        assert await format_repository(client, TREE_ID, "handle123") == ""

    @pytest.mark.asyncio
    async def test_repo_basic(self):
        client = _mock_client(
            {
                "GET_REPOSITORY": {
                    "gramps_id": "R0001",
                    "name": "Local Library",
                    "type": "Library",
                    "urls": [],
                    "note_list": [],
                }
            }
        )
        result = await format_repository(client, TREE_ID, "handle123")
        assert "Library" in result
        assert "Local Library" in result
        assert "R0001" in result

    @pytest.mark.asyncio
    async def test_repo_with_urls(self):
        client = _mock_client(
            {
                "GET_REPOSITORY": {
                    "gramps_id": "R0002",
                    "name": "Archives",
                    "type": "Archive",
                    "urls": [{"path": "https://example.com", "desc": "Homepage"}],
                    "note_list": [],
                }
            }
        )
        result = await format_repository(client, TREE_ID, "handle123")
        assert "https://example.com" in result
        assert "Homepage" in result

    @pytest.mark.asyncio
    async def test_repo_with_notes(self):
        client = _mock_client(
            {
                "GET_REPOSITORY": {
                    "gramps_id": "R0003",
                    "name": "Church",
                    "type": "Church",
                    "urls": [],
                    "note_list": ["note_handle_1"],
                    "extended": {
                        "notes": [{"gramps_id": "N0010", "type": "General"}],
                    },
                },
            }
        )
        result = await format_repository(client, TREE_ID, "handle123")
        assert "Attached notes" in result
        assert "N0010" in result

    @pytest.mark.asyncio
    async def test_repo_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        assert await format_repository(client, TREE_ID, "handle123") == ""


# ============================================================
# place_handler
# ============================================================


class TestFormatPlace:
    """Test format_place handler."""

    @pytest.mark.asyncio
    async def test_empty_handle_inline(self):
        client = _mock_client({})
        assert await format_place(client, TREE_ID, "", inline=True) == ""

    @pytest.mark.asyncio
    async def test_empty_handle_full(self):
        client = _mock_client({})
        result = await format_place(client, TREE_ID, "", inline=False)
        assert "No handle provided" in result

    @pytest.mark.asyncio
    async def test_place_not_found_inline(self):
        client = _mock_client({"GET_PLACE": None})
        assert await format_place(client, TREE_ID, "handle123", inline=True) == ""

    @pytest.mark.asyncio
    async def test_place_not_found_full(self):
        client = _mock_client({"GET_PLACE": None})
        result = await format_place(client, TREE_ID, "handle123", inline=False)
        assert "Place not found" in result

    @pytest.mark.asyncio
    async def test_place_with_title(self):
        client = _mock_client(
            {
                "GET_PLACE": {
                    "gramps_id": "P0001",
                    "title": "Boston, MA, USA",
                    "place_type": "City",
                    "urls": [],
                    "name": {},
                    "placeref_list": [],
                }
            }
        )
        result = await format_place(client, TREE_ID, "handle123", inline=True)
        assert "Boston, MA, USA" in result

    @pytest.mark.asyncio
    async def test_place_full_format(self):
        client = _mock_client(
            {
                "GET_PLACE": {
                    "gramps_id": "P0001",
                    "title": "Boston, MA, USA",
                    "place_type": "City",
                    "urls": [
                        {"path": "https://boston.gov", "desc": "City site"}
                    ],
                    "name": {},
                    "placeref_list": [],
                }
            }
        )
        result = await format_place(client, TREE_ID, "handle123", inline=False)
        assert "City" in result
        assert "P0001" in result
        assert "https://boston.gov" in result

    @pytest.mark.asyncio
    async def test_place_hierarchy_from_name(self):
        # Place with no title but name + parent
        client = _mock_client(
            {
                "GET_PLACE": [
                    {
                        "gramps_id": "P0002",
                        "title": "",
                        "place_type": "City",
                        "urls": [],
                        "name": {"value": "Springfield"},
                        "placeref_list": [{"ref": "parent_handle"}],
                    },
                    {
                        "title": "Illinois, USA",
                        "name": {"value": "Illinois"},
                        "placeref_list": [],
                    },
                ]
            }
        )
        result = await format_place(client, TREE_ID, "handle123", inline=True)
        assert "Springfield" in result

    @pytest.mark.asyncio
    async def test_place_api_error_inline(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        assert await format_place(client, TREE_ID, "handle123", inline=True) == ""

    @pytest.mark.asyncio
    async def test_place_api_error_full(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_place(client, TREE_ID, "handle123", inline=False)
        assert result == ""

    @pytest.mark.asyncio
    async def test_place_format_error_non_inline_returns_empty(self):
        """Broken place record (e.g. orphaned parent handle) returns empty string."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("Record not found"))
        result = await format_place(client, TREE_ID, "broken_handle", inline=False)
        assert result == ""
        assert "error" not in result.lower()


# ============================================================
# citation_handler
# ============================================================


class TestFormatCitation:
    """Test format_citation handler."""

    @pytest.mark.asyncio
    async def test_empty_handle(self):
        client = _mock_client({})
        result = await format_citation(client, TREE_ID, "")
        assert "Unknown Citation" in result

    @pytest.mark.asyncio
    async def test_citation_not_found(self):
        client = _mock_client({"GET_CITATION": None})
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Citation not found" in result

    @pytest.mark.asyncio
    async def test_citation_basic(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0001",
                    "page": "Page 42",
                    "source_handle": "src_handle",
                    "date": None,
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                },
                "GET_SOURCE": {"title": "Census 1900"},
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Census 1900" in result
        assert "Page 42" in result
        assert "C0001" in result

    @pytest.mark.asyncio
    async def test_citation_with_date(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0002",
                    "page": "",
                    "source_handle": "",
                    "date": {"dateval": [0, 0, 1900, False]},
                    "media_list": [],
                    "note_list": [],
                    "extended": {},
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "1900" in result

    @pytest.mark.asyncio
    async def test_citation_with_backlinks(self):
        client = _mock_client(
            {
                "GET_CITATION": {
                    "gramps_id": "C0003",
                    "page": "p. 5",
                    "source_handle": "",
                    "date": None,
                    "media_list": [],
                    "note_list": [],
                    "extended": {
                        "backlinks": {
                            "person": [{"gramps_id": "I0001"}],
                            "event": [{"gramps_id": "E0001"}],
                        }
                    },
                },
            }
        )
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Attached to" in result
        assert "I0001" in result
        assert "E0001" in result

    @pytest.mark.asyncio
    async def test_citation_api_error(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_citation(client, TREE_ID, "handle123")
        assert "Error formatting citation" in result


# ============================================================
# event_handler
# ============================================================


class TestFormatEvent:
    """Test format_event handler."""

    @pytest.mark.asyncio
    async def test_empty_handle_inline(self):
        client = _mock_client({})
        assert await format_event(client, TREE_ID, "", event_label="Born") is None

    @pytest.mark.asyncio
    async def test_empty_handle_full(self):
        client = _mock_client({})
        result = await format_event(client, TREE_ID, "")
        assert "Unknown Event" in result

    @pytest.mark.asyncio
    async def test_event_not_found_inline(self):
        client = _mock_client({"GET_EVENT": None})
        assert (
            await format_event(client, TREE_ID, "handle123", event_label="Born") is None
        )

    @pytest.mark.asyncio
    async def test_event_not_found_full(self):
        client = _mock_client({"GET_EVENT": None})
        result = await format_event(client, TREE_ID, "handle123")
        assert "Event not found" in result

    @pytest.mark.asyncio
    async def test_event_inline_format(self):
        client = _mock_client(
            {
                "GET_EVENT": {
                    "gramps_id": "E0001",
                    "type": "Birth",
                    "date": {"dateval": [15, 6, 1878, False]},
                    "place": "",
                    "citation_list": [],
                    "note_list": [],
                    "extended": {},
                },
            }
        )
        result = await format_event(client, TREE_ID, "handle123", event_label="Born")
        assert result.startswith("Born:")
        assert "1878" in result

    @pytest.mark.asyncio
    async def test_event_full_format(self):
        client = _mock_client(
            {
                "GET_EVENT": {
                    "gramps_id": "E0001",
                    "type": "Birth",
                    "date": {"dateval": [15, 6, 1878, False]},
                    "place": "",
                    "citation_list": [],
                    "note_list": [],
                    "extended": {
                        "backlinks": {
                            "person": [
                                {
                                    "gramps_id": "I0001",
                                    "primary_name": {
                                        "first_name": "John",
                                        "surname_list": [{"surname": "Smith"}],
                                    },
                                    "event_ref_list": [
                                        {"ref": "handle123", "role": "Primary"}
                                    ],
                                }
                            ]
                        }
                    },
                },
            }
        )
        result = await format_event(client, TREE_ID, "handle123")
        assert "Birth" in result
        assert "John Smith" in result
        assert "E0001" in result
        assert "Participants" in result

    @pytest.mark.asyncio
    async def test_event_api_error_inline(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        assert (
            await format_event(client, TREE_ID, "handle123", event_label="Born") is None
        )

    @pytest.mark.asyncio
    async def test_event_api_error_full(self):
        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=Exception("error"))
        result = await format_event(client, TREE_ID, "handle123")
        assert "Error formatting event" in result


# ============================================================
# person_handler
# ============================================================


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


# ============================================================
# family_handler
# ============================================================


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


# ============================================================
# family_detail_handler
# ============================================================


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


# ============================================================
# person_detail_handler
# ============================================================


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


# ============================================================
# _format_recent_changes (analysis.py)
# ============================================================


class TestFormatRecentChanges:
    """Test _format_recent_changes formatting logic."""

    @pytest.mark.asyncio
    async def test_empty_transactions(self):
        """Test with no transactions returns 'No recent changes found.'."""
        client = AsyncMock()
        result = await _format_recent_changes([], client, TREE_ID)
        assert result == "No recent changes found."

    @pytest.mark.asyncio
    async def test_deletion_shows_deleted_annotation(self):
        """Test that unresolved handles (deleted objects) get annotated."""
        client = AsyncMock()
        # Simulate 404 — get_gramps_id_from_handle returns the raw handle
        client.make_api_call = AsyncMock(side_effect=Exception("404 Not Found"))

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Delete person",
                "connection": {"user": {"name": "test"}},
                "changes": [
                    {
                        "obj_class": "Person",
                        "obj_handle": "abcdef1234567890abcdef12",
                    }
                ],
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "(deleted)" in result
        assert "abcdef123456..." in result

    @pytest.mark.asyncio
    async def test_numeric_obj_class_resolved(self):
        """Test that numeric obj_class codes are resolved to names."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "P0001"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Add place",
                "connection": {"user": {"name": "test"}},
                "changes": [
                    {
                        "obj_class": 5,
                        "obj_handle": "abc123",
                    }
                ],
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "Place" in result
        assert "P0001" in result
        # Should NOT show the raw numeric code
        assert "- 5:" not in result

    @pytest.mark.asyncio
    async def test_resolved_gramps_id_shown(self):
        """Test that resolved gramps IDs are shown directly."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I0042"})

        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Edit person",
                "connection": {"user": {"name": "admin"}},
                "changes": [
                    {
                        "obj_class": "Person",
                        "obj_handle": "validhandle123",
                    }
                ],
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "I0042" in result
        assert "(deleted)" not in result

    @pytest.mark.asyncio
    async def test_max_three_changes_shown(self):
        """Test that only first 3 changes are shown with overflow note."""
        client = AsyncMock()
        client.make_api_call = AsyncMock(return_value={"gramps_id": "I0001"})

        changes = [
            {"obj_class": "Person", "obj_handle": f"handle{i}"} for i in range(5)
        ]
        transactions = [
            {
                "timestamp": 1710000000,
                "description": "Batch",
                "connection": {"user": {"name": "test"}},
                "changes": changes,
            }
        ]

        result = await _format_recent_changes(transactions, client, TREE_ID)
        assert "... and 2 more" in result
