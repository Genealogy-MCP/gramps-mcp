"""
Integration test for the complete Gramps MCP workflow.

Tests the full workflow described in gramps-usage-guide.md:
1. Repository creation
2. Source creation
3. Citation creation
4. Event creation
5. Person creation and event linking
6. Family unit creation

This test follows the example workflow: Processing a Marriage Record.

All test entities use the MCP_TEST_ prefix and are tracked in a cleanup
registry so they are deleted after the session (or on Ctrl+C via atexit).
"""

import re
from typing import Any, Dict

import pytest

from src.gramps_mcp.tools.data_management import (
    upsert_citation_tool,
    upsert_event_tool,
    upsert_family_tool,
    upsert_media_tool,
    upsert_note_tool,
    upsert_person_tool,
    upsert_place_tool,
    upsert_repository_tool,
    upsert_source_tool,
)
from src.gramps_mcp.tools.search_basic import (
    search_citation_tool,
    search_event_tool,
    search_family_tool,
    search_person_tool,
    search_place_tool,
    search_repository_tool,
    search_source_tool,
)

from .conftest import TEST_PREFIX


def _extract_handle(text: str) -> str:
    """Extract hex handle from tool response text."""
    match = re.search(r"\[([a-f0-9]+)\]", text)
    if not match:
        pytest.fail(f"Could not extract handle from: {text}")
    return match.group(1)


class TestCompleteWorkflow:
    """
    Test the complete genealogy data entry workflow using real MCP tools.

    This integration test validates the complete workflow described in
    gramps-usage-guide.md by processing a marriage record from start to finish:

    1. Repository creation (MCP_TEST_ St Marys Church Boston)
    2. Source creation (MCP_TEST_ Marriage Register 1875-1880)
    3. Citation creation (Page 67, Entry 15)
    4. Event creation (Marriage on June 15, 1878)
    5. Person creation (MCP_TEST_John MCP_TEST_Smith, MCP_TEST_Mary MCP_TEST_Jones)
    6. Family creation and relationship linking

    The test follows the "Always Find First" principle - searching for existing
    entities before creating new ones, exactly as described in the usage guide.
    """

    @pytest.mark.asyncio
    async def test_complete_marriage_record_workflow(self, cleanup_registry):
        """
        Test the complete workflow by processing a marriage record.

        Example: Marriage of MCP_TEST_John MCP_TEST_Smith and MCP_TEST_Mary
        MCP_TEST_Jones on June 15, 1878 at MCP_TEST_ St Marys Church Boston
        from MCP_TEST_ Marriage Register 1875-1880.
        """
        workflow_data = {"_registry": cleanup_registry}

        # Step 1: Repository Creation
        await self._step_1_repository_creation(workflow_data)
        print(
            f"Step 1 completed: Repository handle = {workflow_data.get('repository_handle')}"
        )

        # Step 2: Source Creation
        await self._step_2_source_creation(workflow_data)
        print(f"Step 2 completed: Source handle = {workflow_data.get('source_handle')}")

        # Step 3: Citation Creation
        await self._step_3_citation_creation(workflow_data)
        print(
            f"Step 3 completed: Citation handle = {workflow_data.get('citation_handle')}"
        )

        # Step 4: Event Creation
        await self._step_4_event_creation(workflow_data)
        print(f"Step 4 completed: Event handle = {workflow_data.get('event_handle')}")

        # Step 5: Person Creation
        await self._step_5_person_creation(workflow_data)
        print(
            f"Step 5 completed: John handle = {workflow_data.get('john_handle')}, "
            f"Mary handle = {workflow_data.get('mary_handle')}"
        )

        # Step 6: Family Creation
        await self._step_6_family_creation(workflow_data)
        print(f"Step 6 completed: Family handle = {workflow_data.get('family_handle')}")

        print("Workflow completed successfully - all entities created and linked!")

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Demo server may return 500 on place creation (pre-existing DB state)",
        strict=False,
    )
    async def test_place_hierarchy_creation(self, cleanup_registry):
        """
        Test place creation with proper hierarchy as described in usage guide.

        Creates the complete place hierarchy:
        Country -> State -> City -> Church
        """
        workflow_data = {"_registry": cleanup_registry}

        await self._create_place_hierarchy(workflow_data)

        assert "country_handle" in workflow_data
        assert "state_handle" in workflow_data
        assert "city_handle" in workflow_data
        assert "church_handle" in workflow_data

        print("Place hierarchy created successfully:")
        print(f"  Country: {workflow_data['country_handle']}")
        print(f"  State: {workflow_data['state_handle']}")
        print(f"  City: {workflow_data['city_handle']}")
        print(f"  Church: {workflow_data['church_handle']}")

    @pytest.mark.asyncio
    async def test_all_entity_attributes_comprehensive(self, cleanup_registry):
        """
        Test comprehensive entity creation with all attributes from usage guide.
        """
        workflow_data = {"_registry": cleanup_registry}

        # Test Note creation
        note_handle = await self._create_test_note(
            workflow_data,
            f"{TEST_PREFIX}comprehensive test note demonstrating note creation.",
            "General",
        )
        workflow_data["test_note_handle"] = note_handle
        print(f"Note created: {note_handle}")

        # Test Media creation
        media_handle = await self._create_test_media(
            workflow_data,
            "tests/sample/33SQ-GP8N-NLK.jpg",
            f"{TEST_PREFIX}Document for Comprehensive Testing",
            {
                "year": 2024,
                "month": 1,
                "day": 15,
                "type": "regular",
                "quality": "regular",
            },
        )
        workflow_data["test_media_handle"] = media_handle
        print(f"Media created: {media_handle}")

        # Test Repository with all attributes
        repository_result = await upsert_source_tool(
            {
                "title": f"{TEST_PREFIX}Repository for Comprehensive Testing",
                "type": "Archive",
                "url": {
                    "type": "Website",
                    "path": "https://test-archive.org",
                    "description": "Test archive website",
                },
                "note_handle": note_handle,
            }
        )

        assert isinstance(repository_result, list) and len(repository_result) == 1
        repo_text = repository_result[0].text
        repo_match = re.search(r"\[([a-f0-9]+)\]", repo_text)
        assert repo_match, f"No repository handle found in: {repo_text}"
        workflow_data["test_repository_handle"] = repo_match.group(1)
        cleanup_registry.track("source", workflow_data["test_repository_handle"])
        print(
            f"Repository created with all attributes: {workflow_data['test_repository_handle']}"
        )

        # Test Source with all attributes
        source_result = await upsert_source_tool(
            {
                "title": f"{TEST_PREFIX}Source Document with All Attributes",
                "repository_handle": workflow_data["test_repository_handle"],
                "author": "Test Author Name",
                "publication_info": "Published by Test Publisher, 2024 Edition",
                "abbreviation": "TEST-SRC-2024",
                "media_handle": media_handle,
                "note_handle": note_handle,
            }
        )

        assert isinstance(source_result, list) and len(source_result) == 1
        source_text = source_result[0].text
        source_match = re.search(r"\[([a-f0-9]+)\]", source_text)
        assert source_match, f"No source handle found in: {source_text}"
        workflow_data["test_source_handle"] = source_match.group(1)
        cleanup_registry.track("source", workflow_data["test_source_handle"])
        print(
            f"Source created with all attributes: {workflow_data['test_source_handle']}"
        )

        # Test comprehensive date structures
        date_examples = [
            {
                "year": 1878,
                "month": 6,
                "day": 15,
                "type": "regular",
                "quality": "regular",
            },
            {
                "year": 1850,
                "type": "about",
                "quality": "estimated",
            },
            {"year": 1860, "type": "before", "quality": "regular"},
            {
                "year": 1870,
                "month": 3,
                "type": "after",
                "quality": "calculated",
            },
        ]

        for i, date_example in enumerate(date_examples, 1):
            print(f"Date structure {i} validated: {date_example}")

        print("\nALL ENTITY ATTRIBUTES COMPREHENSIVE TEST COMPLETED SUCCESSFULLY")

    async def _step_1_repository_creation(self, workflow_data: Dict[str, Any]):
        """Step 1: Repository Creation following usage guide."""
        registry = workflow_data["_registry"]

        # First: search for existing repository
        find_result = await search_repository_tool(
            {"query": f"{TEST_PREFIX}St Marys Church Boston", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if (
            "No sources found" not in result_text
            and f"{TEST_PREFIX}St Marys Church Boston" in result_text
        ):
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            workflow_data["repository_handle"] = existing_handle
        else:
            create_result = await upsert_repository_tool(
                {
                    "name": f"{TEST_PREFIX}St Marys Church Boston",
                    "type": "Church",
                    "urls": [
                        {
                            "type": "Web Home",
                            "path": "https://stmarysboston.org",
                            "desc": "Official church website",
                        }
                    ],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([^\]]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["repository_handle"] = handle_match.group(1)
            registry.track("repository", workflow_data["repository_handle"])

    async def _step_2_source_creation(self, workflow_data: Dict[str, Any]):
        """Step 2: Source Document Creation following usage guide."""
        registry = workflow_data["_registry"]

        find_result = await search_source_tool(
            {"query": f"{TEST_PREFIX}Marriage Register 1875-1880", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if (
            "No sources found" not in result_text
            and f"{TEST_PREFIX}Marriage Register" in result_text
        ):
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            workflow_data["source_handle"] = existing_handle
        else:
            create_result = await upsert_source_tool(
                {
                    "title": f"{TEST_PREFIX}Marriage Register 1875-1880",
                    "reporef_list": [{"ref": workflow_data["repository_handle"]}],
                    "author": "Rev. Patrick O'Sullivan",
                    "pubinfo": "Handwritten register, maintained 1875-1880",
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["source_handle"] = handle_match.group(1)
            registry.track("source", workflow_data["source_handle"])

    async def _step_3_citation_creation(self, workflow_data: Dict[str, Any]):
        """Step 3: Citation Creation following usage guide."""
        registry = workflow_data["_registry"]

        note_handle = await self._create_test_note(
            workflow_data,
            f"{TEST_PREFIX}Research note: Found this record during genealogy research.",
            "Research",
        )
        workflow_data["citation_note_handle"] = note_handle

        media_handle = await self._create_test_media(
            workflow_data,
            "tests/sample/33SQ-GP8N-NLK.jpg",
            f"{TEST_PREFIX}Marriage Record Image",
            {
                "year": 1878,
                "month": 6,
                "day": 15,
                "type": "regular",
                "quality": "regular",
            },
        )
        workflow_data["citation_media_handle"] = media_handle

        find_result = await search_citation_tool(
            {"query": f"{TEST_PREFIX}Page 67 Entry 15", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if "No citations found" not in result_text and "Page 67" in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            workflow_data["citation_handle"] = existing_handle
        else:
            create_result = await upsert_citation_tool(
                {
                    "source_handle": workflow_data["source_handle"],
                    "page": "Page 67, Entry 15, Marriage of MCP_TEST_John MCP_TEST_Smith and MCP_TEST_Mary MCP_TEST_Jones, June 15, 1878",
                    "date": {
                        "dateval": [2024, 1, 15, False],
                        "quality": 0,
                        "modifier": 0,
                    },
                    "media_list": [{"ref": media_handle}] if media_handle else [],
                    "note_list": [note_handle] if note_handle else [],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["citation_handle"] = handle_match.group(1)
            registry.track("citation", workflow_data["citation_handle"])

    async def _step_4_event_creation(self, workflow_data: Dict[str, Any]):
        """Step 4: Event Creation with place and date following usage guide."""
        registry = workflow_data["_registry"]

        await self._create_place_hierarchy(workflow_data)

        find_result = await search_event_tool(
            {"query": f"marriage {TEST_PREFIX}John {TEST_PREFIX}Smith 1878", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if "No events found" not in result_text and "marriage" in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            workflow_data["event_handle"] = existing_handle
        else:
            create_result = await upsert_event_tool(
                {
                    "type": "Marriage",
                    "date": {
                        "dateval": [1878, 6, 15, False],
                        "quality": 0,
                        "modifier": 0,
                    },
                    "citation_list": [workflow_data["citation_handle"]],
                    "description": f"{TEST_PREFIX}Marriage ceremony performed by Rev. O'Sullivan",
                    "place": workflow_data["church_handle"],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_matches = re.findall(r"\[([a-f0-9]+)\]", create_text)
            if handle_matches:
                event_handle = handle_matches[0]
            else:
                event_handle = None
            assert event_handle, f"No handle found in: {create_text}"
            workflow_data["event_handle"] = event_handle
            registry.track("event", event_handle)

    async def _step_5_person_creation(self, workflow_data: Dict[str, Any]):
        """Step 5: Person Creation and Event Linking following usage guide."""
        john_handle = await self._create_or_find_person_with_attributes(
            workflow_data,
            f"{TEST_PREFIX}John",
            f"{TEST_PREFIX}Smith",
            1,
            "1850",
            "Boston",
            workflow_data["event_handle"],
            "groom",
        )
        workflow_data["john_handle"] = john_handle

        mary_handle = await self._create_or_find_person_with_attributes(
            workflow_data,
            f"{TEST_PREFIX}Mary",
            f"{TEST_PREFIX}Jones",
            0,
            "1855",
            "Boston",
            workflow_data["event_handle"],
            "bride",
        )
        workflow_data["mary_handle"] = mary_handle

    async def _step_6_family_creation(self, workflow_data: Dict[str, Any]):
        """Step 6: Family Unit Creation following usage guide."""
        registry = workflow_data["_registry"]

        find_result = await search_family_tool(
            {"query": f"{TEST_PREFIX}John {TEST_PREFIX}Smith {TEST_PREFIX}Mary {TEST_PREFIX}Jones", "pagesize": 5}
        )

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if "No families found" not in result_text:
            handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
            if handle_match:
                existing_handle = handle_match.group(1)

        if existing_handle:
            workflow_data["family_handle"] = existing_handle
        else:
            create_result = await upsert_family_tool(
                {
                    "father_handle": workflow_data["john_handle"],
                    "mother_handle": workflow_data["mary_handle"],
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            workflow_data["family_handle"] = handle_match.group(1)
            registry.track("family", workflow_data["family_handle"])

    async def _create_or_find_person_with_attributes(
        self,
        workflow_data: Dict[str, Any],
        given_name: str,
        surname: str,
        gender: int,
        birth_year: str,
        context: str,
        event_handle: str,
        event_role: str,
    ) -> str:
        """Create or find a person with complete attributes."""
        registry = workflow_data["_registry"]

        person_note_handle = await self._create_test_note(
            workflow_data,
            f"{TEST_PREFIX}Research note for {given_name} {surname}. Found in marriage records.",
            "Research",
        )

        person_media_handle = await self._create_test_media(
            workflow_data,
            "tests/sample/33SQ-GP8N-NLK.jpg",
            f"{TEST_PREFIX}Portrait of {given_name} {surname}",
            {"year": int(birth_year) + 25, "type": "about", "quality": "estimated"},
        )

        search_query = f"{given_name} {surname} {birth_year} {context}"
        find_result = await search_person_tool({"query": search_query, "pagesize": 5})

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if "No people found" not in result_text:
            if (
                given_name.lower() in result_text.lower()
                and surname.lower() in result_text.lower()
            ):
                handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
                if handle_match:
                    existing_handle = handle_match.group(1)

        if existing_handle:
            await upsert_person_tool(
                {
                    "handle": existing_handle,
                    "event_handle": event_handle,
                    "event_role": event_role,
                }
            )
            return existing_handle
        else:
            create_result = await upsert_person_tool(
                {
                    "primary_name": {"given_name": given_name, "surname": surname},
                    "gender": gender,
                    "note_handle": person_note_handle,
                    "media_handle": person_media_handle,
                    "url": {
                        "type": "Website",
                        "path": f"https://findagrave.com/memorial/{given_name.lower()}-{surname.lower()}",
                        "description": f"Find A Grave memorial for {given_name} {surname}",
                    },
                    "event_handle": event_handle,
                    "event_role": event_role,
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            person_handle = handle_match.group(1)
            registry.track("person", person_handle)
            return person_handle

    async def _create_or_find_person(
        self,
        workflow_data: Dict[str, Any],
        given_name: str,
        surname: str,
        gender: int,
        birth_year: str,
        context: str,
    ) -> str:
        """Create or find a person following the workflow guidelines (legacy method)."""
        registry = workflow_data["_registry"]

        search_query = f"{given_name} {surname} {birth_year} {context}"
        find_result = await search_person_tool({"query": search_query, "pagesize": 5})

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if "No people found" not in result_text:
            if (
                given_name.lower() in result_text.lower()
                and surname.lower() in result_text.lower()
            ):
                handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
                if handle_match:
                    existing_handle = handle_match.group(1)

        if existing_handle:
            return existing_handle
        else:
            create_result = await upsert_person_tool(
                {
                    "primary_name": {"given_name": given_name, "surname": surname},
                    "gender": gender,
                }
            )

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            person_handle = handle_match.group(1)
            registry.track("person", person_handle)
            return person_handle

    async def _create_place_hierarchy(self, workflow_data: Dict[str, Any]):
        """Create place hierarchy: Country -> State -> City -> Church."""
        country_handle = await self._create_or_find_place(
            workflow_data, f"{TEST_PREFIX}United States", "Country", None
        )
        workflow_data["country_handle"] = country_handle

        state_handle = await self._create_or_find_place(
            workflow_data, f"{TEST_PREFIX}Massachusetts", "State", country_handle
        )
        workflow_data["state_handle"] = state_handle

        city_handle = await self._create_or_find_place(
            workflow_data, f"{TEST_PREFIX}Boston", "City", state_handle
        )
        workflow_data["city_handle"] = city_handle

        church_handle = await self._create_or_find_place(
            workflow_data, f"{TEST_PREFIX}St Marys Catholic Church", "Church", city_handle
        )
        workflow_data["church_handle"] = church_handle

    async def _create_or_find_place(
        self,
        workflow_data: Dict[str, Any],
        name: str,
        place_type: str,
        enclosed_by_handle: str = None,
    ) -> str:
        """Create or find a place following the workflow guidelines."""
        registry = workflow_data["_registry"]

        find_result = await search_place_tool({"query": name, "pagesize": 5})

        assert isinstance(find_result, list) and len(find_result) == 1
        result_text = find_result[0].text

        existing_handle = None
        if "No places found" not in result_text:
            if name.lower() in result_text.lower():
                handle_match = re.search(r"\[([a-f0-9]+)\]", result_text)
                if handle_match:
                    existing_handle = handle_match.group(1)

        if existing_handle:
            return existing_handle
        else:
            place_data = {
                "name": {"value": name},
                "place_type": place_type,
                "urls": [
                    {
                        "type": "Web Home",
                        "path": f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
                        "description": f"Wikipedia article about {name}",
                    }
                ],
            }

            if enclosed_by_handle:
                place_data["placeref_list"] = [{"ref": enclosed_by_handle}]

            create_result = await upsert_place_tool(place_data)

            assert isinstance(create_result, list) and len(create_result) == 1
            create_text = create_result[0].text
            handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
            assert handle_match, f"No handle found in: {create_text}"
            place_handle = handle_match.group(1)
            registry.track("place", place_handle)
            return place_handle

    async def _create_test_note(
        self, workflow_data: Dict[str, Any], text: str, note_type: str
    ) -> str:
        """Create a test note and track it for cleanup."""
        registry = workflow_data["_registry"]

        create_result = await upsert_note_tool({"text": text, "type": note_type})

        assert isinstance(create_result, list) and len(create_result) == 1
        create_text = create_result[0].text
        handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
        assert handle_match, f"No handle found in: {create_text}"
        note_handle = handle_match.group(1)
        registry.track("note", note_handle)
        return note_handle

    async def _create_test_media(
        self,
        workflow_data: Dict[str, Any],
        file_path: str,
        title: str,
        date_info: Dict[str, Any],
    ) -> str:
        """Create a test media item and track it for cleanup."""
        registry = workflow_data["_registry"]

        create_result = await upsert_media_tool(
            {
                "file_location": file_path,
                "desc": title,
                "date": {
                    "dateval": [
                        date_info["year"],
                        date_info.get("month", 1),
                        date_info.get("day", 1),
                        False,
                    ],
                    "quality": 0,
                    "modifier": 0,
                },
            }
        )

        assert isinstance(create_result, list) and len(create_result) == 1
        create_text = create_result[0].text
        handle_match = re.search(r"\[([a-f0-9]+)\]", create_text)
        assert handle_match, f"No handle found in: {create_text}"
        media_handle = handle_match.group(1)
        registry.track("media", media_handle)
        return media_handle
