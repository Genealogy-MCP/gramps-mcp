"""Unit tests for event_handler formatting functions.

Tests format_event with mock API responses (no network calls).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import _mock_client

from src.gramps_mcp.handlers.event_handler import format_event

TREE_ID = "test-tree"


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
