"""
Unit tests for the operation registry (Code Mode architecture).

Tests cover: registry completeness, search algorithm scoring, and
parameter summarization. No network required.
"""

import pytest

from src.gramps_mcp.operations import (
    OPERATION_REGISTRY,
    OperationEntry,
    search_operations,
    summarize_params,
)

# Expected operation names — all 19 from the current tool set
EXPECTED_OPERATIONS = {
    "search",
    "search_text",
    "list_tags",
    "get",
    "get_tree_stats",
    "get_descendants",
    "get_ancestors",
    "get_recent_changes",
    "upsert_person",
    "upsert_family",
    "upsert_event",
    "upsert_place",
    "upsert_source",
    "upsert_citation",
    "upsert_note",
    "upsert_media",
    "upsert_repository",
    "upsert_tag",
    "delete",
}

VALID_CATEGORIES = {"search", "read", "write", "delete", "analysis"}


class TestOperationRegistry:
    """Tests for OPERATION_REGISTRY completeness and correctness."""

    def test_all_19_operations_registered(self):
        """Registry must contain exactly 19 operations."""
        assert len(OPERATION_REGISTRY) == 19

    def test_operation_names_match_expected(self):
        """Registry keys must match the expected operation names."""
        assert set(OPERATION_REGISTRY.keys()) == EXPECTED_OPERATIONS

    def test_all_operations_have_handler_and_schema(self):
        """Every entry must have a callable handler and a Pydantic schema."""
        for name, entry in OPERATION_REGISTRY.items():
            assert callable(entry.handler), f"{name}: handler not callable"
            assert hasattr(entry.params_schema, "model_fields"), (
                f"{name}: params_schema not a Pydantic model"
            )

    def test_all_operations_have_summary_and_category(self):
        """Every entry must have a non-empty summary and valid category."""
        for name, entry in OPERATION_REGISTRY.items():
            assert entry.summary.strip(), f"{name}: empty summary"
            assert entry.description.strip(), f"{name}: empty description"
            assert entry.category in VALID_CATEGORIES, (
                f"{name}: invalid category '{entry.category}'"
            )

    def test_category_values_valid(self):
        """All categories used must be from the valid set."""
        categories_used = {e.category for e in OPERATION_REGISTRY.values()}
        assert categories_used <= VALID_CATEGORIES

    def test_read_only_flags(self):
        """Read-only operations must have read_only=True."""
        read_only_ops = {
            "search",
            "search_text",
            "list_tags",
            "get",
            "get_tree_stats",
            "get_descendants",
            "get_ancestors",
            "get_recent_changes",
        }
        for name in read_only_ops:
            assert OPERATION_REGISTRY[name].read_only is True, (
                f"{name}: should be read_only"
            )

    def test_write_ops_not_read_only(self):
        """Write operations must have read_only=False."""
        write_ops = {
            "upsert_person",
            "upsert_family",
            "upsert_event",
            "upsert_place",
            "upsert_source",
            "upsert_citation",
            "upsert_note",
            "upsert_media",
            "upsert_repository",
            "upsert_tag",
            "delete",
        }
        for name in write_ops:
            assert OPERATION_REGISTRY[name].read_only is False, (
                f"{name}: should not be read_only"
            )

    def test_destructive_flags(self):
        """Only delete should be destructive."""
        assert OPERATION_REGISTRY["delete"].destructive is True
        non_destructive = set(OPERATION_REGISTRY.keys()) - {"delete"}
        for name in non_destructive:
            assert OPERATION_REGISTRY[name].destructive is False, (
                f"{name}: should not be destructive"
            )

    def test_all_entries_are_operation_entry(self):
        """Every value must be an OperationEntry instance."""
        for name, entry in OPERATION_REGISTRY.items():
            assert isinstance(entry, OperationEntry), f"{name}: not an OperationEntry"

    def test_category_distribution(self):
        """Verify expected distribution: 3 search, 2 read, 10 write, 1 delete, 3 analysis."""
        counts = {}
        for entry in OPERATION_REGISTRY.values():
            counts[entry.category] = counts.get(entry.category, 0) + 1
        assert counts == {
            "search": 3,
            "read": 2,
            "write": 10,
            "delete": 1,
            "analysis": 3,
        }


class TestSummarizeParams:
    """Tests for parameter summary generation."""

    def test_person_params_summary(self):
        """PersonData should produce a summary with known fields."""
        from src.gramps_mcp.models.parameters.people_params import PersonData

        result = summarize_params(PersonData)
        names = {p["name"] for p in result}
        assert "first_name" in names or "primary_name" in names
        assert "handle" in names

    def test_required_vs_optional_fields(self):
        """Summary must distinguish required from optional."""
        from src.gramps_mcp.models.parameters.simple_params import SimpleFindParams

        result = summarize_params(SimpleFindParams)
        type_param = next(p for p in result if p["name"] == "type")
        assert type_param["required"] is True

    def test_all_params_have_expected_keys(self):
        """Each param dict must have name, type, required, description."""
        from src.gramps_mcp.models.parameters.simple_params import SimpleFindParams

        result = summarize_params(SimpleFindParams)
        for param in result:
            assert "name" in param
            assert "type" in param
            assert "required" in param
            assert "description" in param

    def test_empty_model_returns_empty_list(self):
        """A model with no fields should return empty list."""
        from pydantic import BaseModel

        class EmptyModel(BaseModel):
            pass

        result = summarize_params(EmptyModel)
        assert result == []


class TestSearchOperations:
    """Tests for search_operations() keyword matching."""

    def test_exact_name_match(self):
        """Exact operation name should score highest."""
        results = search_operations("search")
        assert results[0].name == "search"

    def test_partial_match(self):
        """Query token in operation name should match."""
        results = search_operations("upsert")
        names = {r.name for r in results}
        assert "upsert_person" in names
        assert "upsert_family" in names

    def test_description_match(self):
        """Query tokens in description should produce results."""
        results = search_operations("ancestors")
        names = {r.name for r in results}
        assert "get_ancestors" in names

    def test_category_filter(self):
        """Category filter should restrict results."""
        results = search_operations("", category="delete")
        assert all(r.category == "delete" for r in results)
        assert len(results) == 1

    def test_category_filter_with_query(self):
        """Category + query should both apply."""
        results = search_operations("person", category="write")
        assert all(r.category == "write" for r in results)
        names = {r.name for r in results}
        assert "upsert_person" in names

    def test_no_match_returns_empty(self):
        """Nonsensical query with no matches returns empty."""
        results = search_operations("xyzzy_nonexistent_foobar")
        assert results == []

    def test_max_results_capped(self):
        """Results should not exceed 10."""
        results = search_operations("upsert")
        assert len(results) <= 10

    def test_score_ordering(self):
        """Higher-scoring operations should come first."""
        results = search_operations("search")
        # "search" exact match should beat "search_text"
        assert results[0].name == "search"

    def test_empty_query_with_category_returns_all_in_category(self):
        """Empty query + category returns all operations in that category."""
        results = search_operations("", category="analysis")
        assert len(results) == 3
        assert all(r.category == "analysis" for r in results)

    def test_token_warning_on_heavy_ops(self):
        """Token-heavy operations should have a warning."""
        entry = OPERATION_REGISTRY["get_descendants"]
        assert entry.token_warning is not None
        assert "token" in entry.token_warning.lower()
