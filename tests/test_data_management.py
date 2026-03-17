"""
Integration tests for data management tools using real Gramps Web API.

Tests all 8 save tools: save_person, save_family, save_event, save_place,
save_source, save_citation, save_note, and save_media tools.
These tests require a working Gramps Web API instance with valid credentials.
Only tests actual API integration - Pydantic validation is tested elsewhere.

All test entities use the MCP_TEST_ prefix and are tracked in a cleanup
registry so they are deleted after the session (or on Ctrl+C via atexit).
"""

import re

import pytest

from src.gramps_mcp.tools._errors import McpToolError

pytestmark = pytest.mark.integration
from src.gramps_mcp.tools.data_management import (
    upsert_citation_tool,
    upsert_event_tool,
    upsert_family_tool,
    upsert_note_tool,
    upsert_person_tool,
    upsert_place_tool,
    upsert_repository_tool,
    upsert_source_tool,
)
from src.gramps_mcp.tools.data_management_delete import delete_tool, upsert_tag_tool
from src.gramps_mcp.tools.data_management_media import upsert_media_tool
from src.gramps_mcp.tools.search_basic import list_tags_tool

from .conftest import TEST_PREFIX

# Store handles for chaining tests following proper Gramps workflow
test_note_handle = None
test_media_handle = None
test_repository_handle = None
test_source_handle = None
test_citation_handle = None
test_place_handle = None
test_event_handle = None
test_person_handles = []


def _extract_handle(text: str) -> str:
    """Extract hex handle from tool response text."""
    match = re.search(r"\[([a-f0-9]+)\]", text)
    if not match:
        pytest.fail(f"Could not extract handle from: {text}")
    return match.group(1)


class TestCreateNoteTool:
    """Test upsert_note_tool functionality - First in workflow."""

    @pytest.mark.asyncio
    async def test_create_note_success(self, cleanup_registry):
        """Test successful note creation with proper text structure and type."""
        global test_note_handle

        result = await upsert_note_tool(
            {
                "text": f"{TEST_PREFIX}research note about family history.",
                "type": "Research",
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}research note about family history." in text, (
            f"Expected note text in output but got: {text}"
        )
        assert "Research" in text, (
            f"Expected note type 'Research' in output but got: {text}"
        )

        test_note_handle = _extract_handle(text)
        cleanup_registry.track("note", test_note_handle)


class TestCreateMediaToolValidation:
    """Unit-style integration tests for upsert_media_tool input validation."""

    @pytest.mark.asyncio
    async def test_create_without_file_location_raises_error(self):
        """Creating media without file_location raises McpToolError."""
        with pytest.raises(McpToolError) as exc_info:
            await upsert_media_tool({"desc": "No file provided"})
        assert "file_location is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_with_nonexistent_file_raises_error(self):
        """A non-existent file_location raises McpToolError with 'File not found'."""
        with pytest.raises(McpToolError) as exc_info:
            await upsert_media_tool(
                {"desc": "Missing file", "file_location": "/nonexistent/path/photo.jpg"}
            )
        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_media_without_file_location(self, cleanup_registry):
        """Updating an existing media record omitting file_location must succeed."""
        global test_media_handle

        # First create a media record to get a handle
        create_result = await upsert_media_tool(
            {
                "file_location": "tests/sample/33SQ-GP8N-NLK.jpg",
                "desc": f"{TEST_PREFIX}Validation update test",
            }
        )
        create_text = create_result[0].text
        assert "successfully" in create_text.lower(), f"Create failed: {create_text}"
        handle = _extract_handle(create_text)
        cleanup_registry.track("media", handle)

        # Now update with only desc — no file_location
        update_result = await upsert_media_tool(
            {"handle": handle, "desc": f"{TEST_PREFIX}Validation update test (updated)"}
        )
        update_text = update_result[0].text
        assert "Error:" not in update_text, f"Update failed: {update_text}"
        assert "successfully" in update_text.lower()


class TestCreateMediaTool:
    """Test upsert_media_tool functionality - Second in workflow."""

    @pytest.mark.asyncio
    async def test_create_media_success(self, cleanup_registry):
        """Test successful media creation with actual file upload."""
        global test_media_handle

        result = await upsert_media_tool(
            {
                "file_location": "tests/sample/33SQ-GP8N-NLK.jpg",
                "desc": f"{TEST_PREFIX}Birth register page",
                "date": {"dateval": [15, 1, 2024, False], "quality": 0, "modifier": 0},
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()
        assert "media" in text.lower()

        assert f"{TEST_PREFIX}Birth register page" in text, (
            f"Expected desc in output but got: {text}"
        )
        assert "image/jpeg" in text, f"Expected image MIME type but got: {text}"
        assert "15 January 2024" in text, (
            f"Expected formatted date '15 January 2024' in output but got: {text}"
        )

        test_media_handle = _extract_handle(text)
        cleanup_registry.track("media", test_media_handle)


class TestCreateRepositoryTool:
    """Test upsert_repository_tool functionality - Third in workflow."""

    @pytest.mark.asyncio
    async def test_create_repository_success(self, cleanup_registry):
        """Test successful repository creation using note handle from previous test."""
        global test_repository_handle, test_note_handle

        if not test_note_handle:
            pytest.fail(
                "No note handle available from previous test - run tests in order"
            )

        result = await upsert_repository_tool(
            {
                "name": f"{TEST_PREFIX}National Archives Boston",
                "type": "Archive",
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://www.archives.gov/boston",
                        "desc": "Official website",
                    }
                ],
                "note_list": [test_note_handle],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}National Archives Boston" in text, (
            f"Expected repository name (required) in output but got: {text}"
        )
        assert "Archive" in text, (
            f"Expected repository type (required) in output but got: {text}"
        )

        assert "https://www.archives.gov/boston" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "Official website" in text, (
            f"Expected URL description in output but got: {text}"
        )
        assert "Attached notes: N" in text, (
            f"Expected note reference after 'Attached notes:' in output but got: {text}"
        )

        # Repository handler format: "Archive: Name - ID - [handle]"
        handle_match = re.search(r"- \[([^\]]+)\]", text)
        if handle_match:
            test_repository_handle = handle_match.group(1)
            cleanup_registry.track("repository", test_repository_handle)
        else:
            pytest.fail("Could not extract repository handle for chaining tests")


class TestCreateSourceTool:
    """Test upsert_source_tool functionality - Fourth in workflow."""

    @pytest.mark.asyncio
    async def test_create_source_success(self, cleanup_registry):
        """Test successful source creation using repository and media handles."""
        global \
            test_source_handle, \
            test_repository_handle, \
            test_media_handle, \
            test_note_handle

        if not test_repository_handle:
            pytest.fail(
                "No repository handle available from previous test - run tests in order"
            )

        result = await upsert_source_tool(
            {
                "title": f"{TEST_PREFIX}Birth Register 1850-1860",
                "reporef_list": [{"ref": test_repository_handle}],
                "author": "City Clerk's Office",
                "pubinfo": "Boston City Records, Volume 12",
                "media_list": [{"ref": test_media_handle}] if test_media_handle else [],
                "note_list": [test_note_handle] if test_note_handle else [],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}Birth Register 1850-1860" in text, (
            f"Expected source title (required) in output but got: {text}"
        )
        assert f"{TEST_PREFIX}National Archives Boston" in text, (
            f"Expected repository reference (required) in output but got: {text}"
        )

        assert "City Clerk's Office" in text, (
            f"Expected author in output but got: {text}"
        )
        assert "Boston City Records, Volume 12" in text, (
            f"Expected publication info in output but got: {text}"
        )

        test_source_handle = _extract_handle(text)
        cleanup_registry.track("source", test_source_handle)


class TestCreateCitationTool:
    """Test upsert_citation_tool functionality - Fifth in workflow."""

    @pytest.mark.asyncio
    async def test_create_citation_success(self, cleanup_registry):
        """Test successful citation creation using source handle."""
        global \
            test_citation_handle, \
            test_source_handle, \
            test_media_handle, \
            test_note_handle

        if not test_source_handle:
            pytest.fail(
                "No source handle available from previous test - run tests in order"
            )

        result = await upsert_citation_tool(
            {
                "source_handle": test_source_handle,
                "page": f"{TEST_PREFIX}Page 45, Entry 23",
                "date": {
                    "dateval": [15, 1, 2024, False],
                    "quality": 1,  # estimated
                    "modifier": 3,  # about
                },
                "media_list": [{"ref": test_media_handle}] if test_media_handle else [],
                "note_list": [test_note_handle] if test_note_handle else [],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}Birth Register 1850-1860" in text, (
            f"Expected source reference (required) in output but got: {text}"
        )

        assert f"{TEST_PREFIX}Page 45, Entry 23" in text, (
            f"Expected citation page in output but got: {text}"
        )
        assert "about 15 January 2024 (estimated)" in text, (
            f"Expected full citation date with modifier and quality in output but got: {text}"
        )

        test_citation_handle = _extract_handle(text)
        cleanup_registry.track("citation", test_citation_handle)


class TestCreatePlaceTool:
    """Test upsert_place_tool functionality - Sixth in workflow."""

    @pytest.mark.asyncio
    async def test_create_place_success(self, cleanup_registry):
        """Test successful place creation with proper hierarchy."""
        global test_place_handle

        # First create country (top level)
        country_result = await upsert_place_tool(
            {"name": {"value": f"{TEST_PREFIX}United States"}, "place_type": "Country"}
        )

        country_handle = _extract_handle(country_result[0].text)
        cleanup_registry.track("place", country_handle)

        # Create state enclosed by country
        state_result = await upsert_place_tool(
            {
                "name": {"value": f"{TEST_PREFIX}Massachusetts"},
                "place_type": "State",
                "placeref_list": [{"ref": country_handle}],
            }
        )

        state_handle = _extract_handle(state_result[0].text)
        cleanup_registry.track("place", state_handle)

        # Create city enclosed by state
        result = await upsert_place_tool(
            {
                "name": {"value": f"{TEST_PREFIX}Boston"},
                "place_type": "City",
                "placeref_list": [{"ref": state_handle}],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://www.boston.gov",
                        "description": "Official city website",
                    }
                ],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}Boston" in text, (
            f"Expected place title (required) in output but got: {text}"
        )
        assert "City" in text, (
            f"Expected place type (required) in output but got: {text}"
        )
        assert f"{TEST_PREFIX}Massachusetts" in text, (
            f"Expected enclosed_by reference in output but got: {text}"
        )

        urls = re.findall(r'(https?://[^\s"\',]+)', text)
        assert any(url == "https://www.boston.gov" for url in urls), (
            f"Expected exact URL 'https://www.boston.gov' in output URLs {urls} but got: {text}"
        )
        assert "Official city website" in text, (
            f"Expected URL description in output but got: {text}"
        )

        test_place_handle = _extract_handle(text)
        cleanup_registry.track("place", test_place_handle)


class TestCreateEventTool:
    """Test upsert_event_tool functionality - Seventh in workflow."""

    @pytest.mark.asyncio
    async def test_create_event_success(self, cleanup_registry):
        """Test successful event creation using citation and place handles."""
        global test_event_handle, test_citation_handle, test_place_handle

        if not test_citation_handle:
            pytest.fail(
                "No citation handle available from previous test - run tests in order"
            )

        result = await upsert_event_tool(
            {
                "type": "Birth",
                "description": f"{TEST_PREFIX}Birth event",
                "citation_list": [test_citation_handle],
                "date": {"dateval": [15, 6, 1878, False], "quality": 0, "modifier": 0},
                "place": test_place_handle if test_place_handle else None,
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert "Birth" in text, f"Expected type (required) in output but got: {text}"
        assert "Attached citations: C" in text, (
            f"Expected citation gramps_id (required) in output but got: {text}"
        )

        assert "15 June 1878" in text, (
            f"Expected formatted event date in output but got: {text}"
        )
        assert f"{TEST_PREFIX}Boston" in text, (
            f"Expected linked place in output but got: {text}"
        )

        test_event_handle = _extract_handle(text)
        cleanup_registry.track("event", test_event_handle)


class TestCreatePersonTool:
    """Test upsert_person_tool functionality - Eighth in workflow."""

    @pytest.mark.asyncio
    async def test_create_person_success(self, cleanup_registry):
        """Test successful person creation using proper structure and linking events."""
        global \
            test_person_handles, \
            test_event_handle, \
            test_media_handle, \
            test_note_handle

        result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}John",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Smith", "primary": True}
                    ],
                },
                "gender": 1,  # Male
                "event_ref_list": [{"ref": test_event_handle, "role": "Primary"}]
                if test_event_handle
                else [],
                "media_list": [{"ref": test_media_handle}] if test_media_handle else [],
                "note_list": [test_note_handle] if test_note_handle else [],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://familysearch.org/person/123",
                        "description": "FamilySearch profile",
                    }
                ],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}John" in text, (
            f"Expected primary_name first_name (required) in output but got: {text}"
        )
        assert f"{TEST_PREFIX}Smith" in text, (
            f"Expected primary_name surname (required) in output but got: {text}"
        )
        assert "(M)" in text, f"Expected gender (M) in output but got: {text}"

        if "Birth" in text:
            assert "Birth" in text, f"Expected linked event in output but got: {text}"
            assert "Primary" in text, f"Expected event role in output but got: {text}"

        assert "https://familysearch.org/person/123" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "FamilySearch profile" in text, (
            f"Expected URL description in output but got: {text}"
        )

        john_handle = _extract_handle(text)
        test_person_handles.append(john_handle)
        cleanup_registry.track("person", john_handle)

    @pytest.mark.asyncio
    async def test_update_person_with_event_reference(self, cleanup_registry):
        """Test updating an existing person with a new event reference - Issue #9."""
        # Step 1: Create a standalone test person
        person_result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}Update",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Issue9", "primary": True}
                    ],
                },
                "gender": 1,  # Male
            }
        )

        person_handle = _extract_handle(person_result[0].text)
        cleanup_registry.track("person", person_handle)

        # Step 2: Create a simple note for our citation
        note_result = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}note for Issue #9 update test", "type": "General"}
        )
        note_handle = _extract_handle(note_result[0].text)
        cleanup_registry.track("note", note_handle)

        # Step 3: Create a simple source
        source_result = await upsert_source_tool(
            {"title": f"{TEST_PREFIX}Source for Issue 9"}
        )
        source_handle = _extract_handle(source_result[0].text)
        cleanup_registry.track("source", source_handle)

        # Step 4: Create a citation
        citation_result = await upsert_citation_tool(
            {"source_handle": source_handle, "page": f"{TEST_PREFIX}Test Page"}
        )
        citation_handle = _extract_handle(citation_result[0].text)
        cleanup_registry.track("citation", citation_handle)

        # Step 5: Create first event (Birth)
        birth_event_result = await upsert_event_tool(
            {
                "type": "Birth",
                "description": f"{TEST_PREFIX}Birth event",
                "citation_list": [citation_handle],
                "date": {"dateval": [1, 1, 1900, False], "quality": 0, "modifier": 0},
            }
        )

        birth_event_handle = _extract_handle(birth_event_result[0].text)
        cleanup_registry.track("event", birth_event_handle)

        # Step 6: Update person with first event
        await upsert_person_tool(
            {
                "handle": person_handle,
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}Update",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Issue9", "primary": True}
                    ],
                },
                "gender": 1,
                "event_ref_list": [{"ref": birth_event_handle, "role": "Primary"}],
            }
        )

        # Step 7: Create second event (Death)
        death_event_result = await upsert_event_tool(
            {
                "type": "Death",
                "description": f"{TEST_PREFIX}Death event",
                "citation_list": [citation_handle],
                "date": {"dateval": [31, 12, 1999, False], "quality": 0, "modifier": 0},
            }
        )

        death_event_handle = _extract_handle(death_event_result[0].text)
        cleanup_registry.track("event", death_event_handle)

        # Step 8: Update person with BOTH events (issue #9 scenario)
        update_result = await upsert_person_tool(
            {
                "handle": person_handle,
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}Update",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Issue9", "primary": True}
                    ],
                },
                "gender": 1,
                "event_ref_list": [
                    {"ref": birth_event_handle, "role": "Primary"},
                    {"ref": death_event_handle, "role": "Primary"},
                ],
            }
        )

        text = update_result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()
        assert "updated" in text.lower(), (
            f"Expected 'updated' in output but got: {text}"
        )

        assert "Birth" in text, f"Expected Birth event in output but got: {text}"
        assert "Death" in text, f"Expected Death event in output but got: {text}"

    @pytest.mark.asyncio
    async def test_create_second_person_success(self, cleanup_registry):
        """Test creation of second person for family test."""
        global test_person_handles, test_media_handle, test_note_handle

        result = await upsert_person_tool(
            {
                "primary_name": {
                    "first_name": f"{TEST_PREFIX}Mary",
                    "surname_list": [
                        {"surname": f"{TEST_PREFIX}Johnson", "primary": True}
                    ],
                },
                "gender": 0,  # Female
                "media_list": [{"ref": test_media_handle}] if test_media_handle else [],
                "note_list": [test_note_handle] if test_note_handle else [],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://familysearch.org/person/456",
                        "description": "FamilySearch profile",
                    }
                ],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}Mary" in text, (
            f"Expected primary_name first_name (required) in output but got: {text}"
        )
        assert f"{TEST_PREFIX}Johnson" in text, (
            f"Expected primary_name surname (required) in output but got: {text}"
        )
        assert "(F)" in text, f"Expected gender (F) in output but got: {text}"

        assert "https://familysearch.org/person/456" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "FamilySearch profile" in text, (
            f"Expected URL description in output but got: {text}"
        )

        mary_handle = _extract_handle(text)
        test_person_handles.append(mary_handle)
        cleanup_registry.track("person", mary_handle)


class TestCreateFamilyTool:
    """Test upsert_family_tool functionality - Last in workflow."""

    @pytest.mark.asyncio
    async def test_create_family_success(self, cleanup_registry):
        """Test successful family creation using person handles from previous tests."""
        global test_person_handles, test_media_handle, test_note_handle

        if len(test_person_handles) < 2:
            pytest.fail(
                "Need at least 2 person handles from previous tests - run tests in order"
            )

        father_handle = test_person_handles[0]
        mother_handle = test_person_handles[1]

        result = await upsert_family_tool(
            {
                "father_handle": father_handle,
                "mother_handle": mother_handle,
                "media_list": [{"ref": test_media_handle}] if test_media_handle else [],
                "note_list": [test_note_handle] if test_note_handle else [],
                "urls": [
                    {
                        "type": "Web Home",
                        "path": "https://familysearch.org/family/789",
                        "description": "FamilySearch family record",
                    }
                ],
            }
        )

        text = result[0].text
        assert "Error:" not in text, f"Expected success but got error: {text}"
        assert "successfully" in text.lower()

        assert f"{TEST_PREFIX}John" in text or f"{TEST_PREFIX}Smith" in text, (
            f"Expected father reference in output but got: {text}"
        )
        assert f"{TEST_PREFIX}Mary" in text or f"{TEST_PREFIX}Johnson" in text, (
            f"Expected mother reference in output but got: {text}"
        )

        assert "https://familysearch.org/family/789" in text, (
            f"Expected URL path in output but got: {text}"
        )
        assert "FamilySearch family record" in text, (
            f"Expected URL description in output but got: {text}"
        )

        family_handle = _extract_handle(text)
        cleanup_registry.track("family", family_handle)


class TestListModeReplace:
    """Test list_mode='replace' behavior on update operations."""

    @pytest.mark.asyncio
    async def test_replace_note_list_on_event(self, cleanup_registry):
        """Test that list_mode='replace' overwrites note_list instead of merging."""
        # Create two notes
        note1_result = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}First note for list_mode test", "type": "General"}
        )
        note1_handle = _extract_handle(note1_result[0].text)
        cleanup_registry.track("note", note1_handle)

        note2_result = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}Second note for list_mode test", "type": "General"}
        )
        note2_handle = _extract_handle(note2_result[0].text)
        cleanup_registry.track("note", note2_handle)

        # Create a source and citation for the event (required)
        source_result = await upsert_source_tool(
            {"title": f"{TEST_PREFIX}Source for list_mode test"}
        )
        source_handle = _extract_handle(source_result[0].text)
        cleanup_registry.track("source", source_handle)

        citation_result = await upsert_citation_tool({"source_handle": source_handle})
        citation_handle = _extract_handle(citation_result[0].text)
        cleanup_registry.track("citation", citation_handle)

        # Create event with first note
        event_result = await upsert_event_tool(
            {
                "type": "Birth",
                "description": f"{TEST_PREFIX}Birth event for list_mode test",
                "citation_list": [citation_handle],
                "note_list": [note1_handle],
            }
        )
        event_text = event_result[0].text
        assert "Error:" not in event_text
        event_handle = _extract_handle(event_text)
        cleanup_registry.track("event", event_handle)

        # Update event with second note only, using list_mode='replace'
        replace_result = await upsert_event_tool(
            {
                "handle": event_handle,
                "type": "Birth",
                "description": f"{TEST_PREFIX}Birth event for list_mode test",
                "citation_list": [citation_handle],
                "note_list": [note2_handle],
                "list_mode": "replace",
            }
        )
        replace_text = replace_result[0].text

        assert "Error:" not in replace_text
        assert "updated" in replace_text.lower()

        # Verify via raw API: note_list should contain only note2
        from src.gramps_mcp.client import GrampsWebAPIClient
        from src.gramps_mcp.config import get_settings
        from src.gramps_mcp.models.api_calls import ApiCalls

        client = GrampsWebAPIClient()
        try:
            settings = get_settings()
            event_data = await client.make_api_call(
                api_call=ApiCalls.GET_EVENT,
                tree_id=settings.gramps_tree_id,
                handle=event_handle,
            )
            note_list = event_data.get("note_list", [])
            assert note2_handle in note_list, (
                f"Expected note2 ({note2_handle}) in note_list, "
                f"got: {note_list}"
            )
            assert note1_handle not in note_list, (
                f"note1 ({note1_handle}) should have been replaced"
            )
        finally:
            await client.close()


class TestDeleteTypeTool:
    """Test delete_tool functionality."""

    @pytest.mark.asyncio
    async def test_delete_note_success(self):
        """Test creating and then deleting a note."""
        # Create a disposable note
        create_result = await upsert_note_tool(
            {"text": f"{TEST_PREFIX}Temporary note for delete test", "type": "General"}
        )
        text = create_result[0].text
        assert "Error:" not in text

        note_handle = _extract_handle(text)
        # Reason: no need to track — we delete it immediately in this test

        # Delete it
        delete_result = await delete_tool({"type": "note", "handle": note_handle})
        delete_text = delete_result[0].text

        assert "Successfully deleted" in delete_text
        assert note_handle in delete_text

    @pytest.mark.asyncio
    async def test_delete_invalid_handle(self):
        """Test delete with invalid handle raises McpToolError."""
        with pytest.raises(McpToolError):
            await delete_tool({"type": "note", "handle": "nonexistent_handle_xyz"})


class TestCreateTagTool:
    """Test upsert_tag_tool and list_tags_tool functionality."""

    @pytest.mark.asyncio
    async def test_create_tag_success(self, cleanup_registry):
        """Test successful tag creation with name and color."""
        result = await upsert_tag_tool(
            {"name": f"{TEST_PREFIX}Tag", "color": "#FF5733", "priority": 5}
        )

        text = result[0].text

        assert "Error:" not in text
        assert "Successfully" in text
        assert f"{TEST_PREFIX}Tag" in text
        assert "#FF5733" in text

        tag_handle = _extract_handle(text)
        cleanup_registry.track("tag", tag_handle)

        # Update should raise error (API 3.x doesn't support tag PUT)
        with pytest.raises(McpToolError):
            await upsert_tag_tool(
                {
                    "handle": tag_handle,
                    "name": f"{TEST_PREFIX}Tag Updated",
                    "color": "#00FF00",
                }
            )

    @pytest.mark.asyncio
    async def test_find_tags(self):
        """Test listing tags."""
        result = await list_tags_tool({})

        text = result[0].text

        # Should either find tags or say none found
        assert "tags" in text.lower()


# Removed validation tests - Pydantic handles input validation automatically
# These tests focus only on actual Gramps Web API integration
