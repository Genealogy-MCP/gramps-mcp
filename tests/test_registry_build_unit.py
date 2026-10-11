"""
Unit tests for table-driven registry assembly (#101, slice S2 of #99).

No Docker, no network: the tests read the generated resource table and
build registries from small in-memory overlays.
"""

from dataclasses import replace

import pytest
from pydantic import BaseModel

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.simple_params import (
    DeletableEntityType,
    EntityType,
)
from src.gramps_mcp.registry_build import OpOverlay, build_registry, merge_registry
from src.gramps_mcp.resource_table import ENTITY_RESOURCES

# Registry order before S2; the merged registry must keep it (search output
# with an empty query lists operations in registry order).
_EXPECTED_ORDER = [
    "search",
    "search_text",
    "list_tags",
    "get",
    "get_tree_stats",
    "download_media",
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
    "get_ancestors",
    "get_descendants",
    "get_recent_changes",
]


class _Params(BaseModel):
    """Throwaway params schema for overlay tests."""

    type: str


async def _handler(ctx=None, params=None):
    """Throwaway handler for overlay tests."""
    return []


def _overlay(**overrides) -> OpOverlay:
    """Build a valid overlay, overridable per test."""
    values = dict(
        name="probe",
        summary="Probe summary",
        description="Probe description",
        category="read",
        params_schema=_Params,
        handler=_handler,
        read_only=True,
        destructive=False,
        scope="item",
        verb="GET",
        entities=("person", "tag"),
    )
    values.update(overrides)
    return OpOverlay(**values)


class TestBuildRegistry:
    """build_registry turns overlays into OperationEntry objects."""

    def test_builds_entry_from_overlay(self):
        """Every overlay field lands on the entry, keyed by name."""
        registry = build_registry(ENTITY_RESOURCES, (_overlay(),))
        entry = registry["probe"]
        assert (
            list(registry),
            entry.name,
            entry.summary,
            entry.description,
            entry.category,
            entry.params_schema,
            entry.handler,
            entry.read_only,
            entry.destructive,
        ) == (
            ["probe"],
            "probe",
            "Probe summary",
            "Probe description",
            "read",
            _Params,
            _handler,
            True,
            False,
        )

    def test_unknown_entity_rejected(self):
        """An overlay naming an entity absent from the table fails fast."""
        with pytest.raises(ValueError, match="unicorn"):
            build_registry(ENTITY_RESOURCES, (_overlay(entities=("unicorn",)),))

    def test_unsupported_verb_rejected(self):
        """An overlay whose verb the table does not list fails fast."""
        table = dict(ENTITY_RESOURCES)
        table["tag"] = replace(table["tag"], item_verbs=("GET",))
        with pytest.raises(ValueError, match="DELETE"):
            build_registry(table, (_overlay(verb="DELETE"),))

    def test_unknown_scope_rejected(self):
        """Scope must be 'collection' or 'item'."""
        with pytest.raises(ValueError, match="scope"):
            build_registry(ENTITY_RESOURCES, (_overlay(scope="nested"),))

    def test_duplicate_overlay_name_rejected(self):
        """Two overlays with one name collide."""
        with pytest.raises(ValueError, match="probe"):
            build_registry(ENTITY_RESOURCES, (_overlay(), _overlay()))


class TestMergeRegistry:
    """merge_registry joins handwritten and generated entries in order."""

    def test_collision_rejected(self):
        """A name present in both halves fails."""
        generated = build_registry(ENTITY_RESOURCES, (_overlay(),))
        with pytest.raises(ValueError, match="probe"):
            merge_registry(dict(generated), generated, ["probe"])

    def test_order_must_cover_every_name(self):
        """The order list must name exactly the merged operations."""
        generated = build_registry(ENTITY_RESOURCES, (_overlay(),))
        with pytest.raises(ValueError, match="order"):
            merge_registry({}, generated, ["probe", "ghost"])

    def test_order_preserved(self):
        """Entries come out in the order given."""
        first = build_registry(ENTITY_RESOURCES, (_overlay(name="a"),))
        second = build_registry(ENTITY_RESOURCES, (_overlay(name="b"),))
        merged = merge_registry(second, first, ["b", "a"])
        assert list(merged) == ["b", "a"]


class TestOperationRegistry:
    """The live registry merges the table-driven reads with handwritten ops."""

    def test_count_and_order_unchanged(self):
        """Still 20 operations, in the pre-S2 order."""
        from src.gramps_mcp.operations import OPERATION_REGISTRY

        assert list(OPERATION_REGISTRY) == _EXPECTED_ORDER

    def test_reads_and_delete_come_from_table(self):
        """search, list_tags, get and delete are the build_registry entries."""
        from src.gramps_mcp.operations import OPERATION_REGISTRY, TABLE_OPERATIONS

        assert {
            name: OPERATION_REGISTRY[name] is entry
            for name, entry in TABLE_OPERATIONS.items()
        } == {"search": True, "list_tags": True, "get": True, "delete": True}

    def test_overlay_entities_match_param_enums(self):
        """Overlays cover exactly the entity enums the params schemas accept."""
        from src.gramps_mcp.operation_overlays import TABLE_OVERLAYS

        assert {o.name: set(o.entities) for o in TABLE_OVERLAYS} == {
            "search": {e.value for e in EntityType},
            "list_tags": {"tag"},
            "get": {e.value for e in EntityType},
            "delete": {e.value for e in DeletableEntityType},
        }


class TestTableRoutes:
    """Endpoint lookups come from the resource table, not per-entity code."""

    def test_collection_call_from_table(self):
        """The list endpoint resolves to the matching ApiCalls member."""
        from src.gramps_mcp.tools.table_routes import collection_call

        assert [collection_call(e) for e in ("person", "media", "tag")] == [
            ApiCalls.GET_PEOPLE,
            ApiCalls.GET_MEDIA,
            ApiCalls.GET_TAGS,
        ]

    def test_item_call_from_table(self):
        """The item endpoint resolves to the matching ApiCalls member."""
        from src.gramps_mcp.tools.table_routes import item_call

        assert [item_call(e, "DELETE") for e in ("media", "tag")] == [
            ApiCalls.DELETE_MEDIA_ITEM,
            ApiCalls.DELETE_TAG,
        ]

    def test_path_follows_table_row(self):
        """A changed row path changes the resolved endpoint."""
        from src.gramps_mcp.tools.table_routes import collection_call

        table = {
            "person": replace(ENTITY_RESOURCES["person"], collection_path="notes/")
        }
        assert collection_call("person", table=table) is ApiCalls.GET_NOTES

    def test_verb_missing_from_table_rejected(self):
        """A verb the row does not list raises."""
        from src.gramps_mcp.tools.table_routes import item_call

        table = {"tag": replace(ENTITY_RESOURCES["tag"], item_verbs=("GET",))}
        with pytest.raises(ValueError, match="DELETE"):
            item_call("tag", "DELETE", table=table)

    def test_unknown_entity_rejected(self):
        """An entity absent from the table raises."""
        from src.gramps_mcp.tools.table_routes import collection_call

        with pytest.raises(ValueError, match="unicorn"):
            collection_call("unicorn")

    def test_list_params_must_be_in_table(self):
        """A params class field the table does not list is rejected."""
        from src.gramps_mcp.tools.table_routes import check_list_params

        class _Bogus(BaseModel):
            not_a_list_param: int = 0

        with pytest.raises(ValueError, match="not_a_list_param"):
            check_list_params(_Bogus, "person")

    def test_overlay_params_are_table_list_params(self):
        """Every read overlay's params class passes the table check."""
        from src.gramps_mcp.tools.table_routes import READ_OVERLAYS, check_list_params

        assert [
            check_list_params(o.params_class, e) for e, o in READ_OVERLAYS.items()
        ] == [None] * len(READ_OVERLAYS)

    def test_delete_map_derived_from_table(self):
        """DELETE_API_CALLS covers every table row with a DELETE item verb."""
        from src.gramps_mcp.tools.data_management_delete import DELETE_API_CALLS

        assert DELETE_API_CALLS == {
            entity: ApiCalls(("DELETE", row.item_path))
            for entity, row in ENTITY_RESOURCES.items()
        }

    def test_resolve_map_derived_from_table(self):
        """gramps_id resolution uses the table list endpoint per entity."""
        from src.gramps_mcp.tools._resolve import _RESOLVE_DISPATCH
        from src.gramps_mcp.tools.table_routes import READ_OVERLAYS

        assert _RESOLVE_DISPATCH == {
            entity: (
                overlay.params_class,
                ApiCalls(("GET", ENTITY_RESOURCES[entity].collection_path)),
            )
            for entity, overlay in READ_OVERLAYS.items()
        }
