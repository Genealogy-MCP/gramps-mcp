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
                    "urls": [{"path": "https://boston.gov", "desc": "City site"}],
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


# ============================================================
# person_handler — extended branches
# ============================================================


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


# ============================================================
# family_handler — extended branches
# ============================================================


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


# ============================================================
# event_handler — extended branches
# ============================================================


class TestFormatEventExtended:
    """Test format_event with family backlinks, citations, notes."""

    @pytest.mark.asyncio
    async def test_event_with_family_backlinks(self):
        """Marriage event with family backlink resolves father and mother."""

        async def mock_call(api_call, tree_id=None, handle=None, params=None):
            name = api_call.name if hasattr(api_call, "name") else str(api_call)
            if name == "GET_EVENT":
                return {
                    "gramps_id": "E0100",
                    "type": "Marriage",
                    "date": {"dateval": [10, 6, 1880, False]},
                    "place": "",
                    "extended": {
                        "backlinks": {
                            "family": [
                                {
                                    "gramps_id": "F0001",
                                    "father_handle": "father_h",
                                    "mother_handle": "mother_h",
                                    "event_ref_list": [
                                        {"ref": "evt_handle", "role": "Family"}
                                    ],
                                }
                            ]
                        }
                    },
                }
            if name == "GET_PERSON":
                if handle == "father_h":
                    return {
                        "gramps_id": "I0001",
                        "primary_name": {
                            "first_name": "John",
                            "surname_list": [{"surname": "Smith"}],
                        },
                    }
                if handle == "mother_h":
                    return {
                        "gramps_id": "I0002",
                        "primary_name": {
                            "first_name": "Mary",
                            "surname_list": [{"surname": "Jones"}],
                        },
                    }
            return {}

        client = AsyncMock()
        client.make_api_call = AsyncMock(side_effect=mock_call)
        result = await format_event(client, TREE_ID, "evt_handle")
        assert "Marriage" in result
        assert "John Smith & Mary Jones" in result
        assert "Husband (I0001)" in result
        assert "Wife (I0002)" in result

    @pytest.mark.asyncio
    async def test_event_with_citations_and_notes(self):
        client = _mock_client(
            {
                "GET_EVENT": {
                    "gramps_id": "E0200",
                    "type": "Birth",
                    "date": {"dateval": [15, 6, 1878, False]},
                    "place": "place_h",
                    "extended": {
                        "backlinks": {},
                        "citations": [{"gramps_id": "C0001"}],
                        "notes": [{"gramps_id": "N0001"}],
                    },
                },
                "GET_PLACE": {
                    "title": "Boston",
                    "name": {},
                    "placeref_list": [],
                },
            }
        )
        result = await format_event(client, TREE_ID, "evt_handle")
        assert "Attached citations: C0001" in result
        assert "Attached notes: N0001" in result
        assert "Boston" in result

    @pytest.mark.asyncio
    async def test_event_date_place_display(self):
        """Full format shows date-place on second line."""
        client = _mock_client(
            {
                "GET_EVENT": {
                    "gramps_id": "E0300",
                    "type": "Census",
                    "date": {"dateval": [0, 0, 1900, False]},
                    "place": "",
                    "extended": {"backlinks": {}},
                },
            }
        )
        result = await format_event(client, TREE_ID, "evt_handle")
        assert "1900" in result
        assert "Census" in result


# ============================================================
# person_detail_handler — extended branches
# ============================================================


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


# ============================================================
# family_detail_handler — extended branches
# ============================================================


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
