"""
Unit tests for the schema snapshot, codegen and the generated resource table.

No Docker, no network: the snapshot and sidecar are read from the checkout,
and the table-shape tests use a small in-memory spec.
"""

import hashlib
import json

import pytest

from src.gramps_mcp import codegen
from src.gramps_mcp.resource_policy import (
    ENTITY_COMPONENTS,
    PERSON_SCHEMA_FIELDS,
    READ_ONLY_FIELDS,
)
from src.gramps_mcp.resource_rows import EntityResource, FieldSpec, ListParam
from src.gramps_mcp.schema_pin import SCHEMA_VERSION

ENTITY_NAMES = (
    "person",
    "family",
    "event",
    "place",
    "citation",
    "source",
    "repository",
    "media",
    "note",
    "tag",
)


class TestPin:
    """The code pin must equal what the checked-in snapshot describes."""

    def test_pin_matches_sidecar_version(self):
        """Sidecar gramps_webapi_version equals SCHEMA_VERSION."""
        sidecar = codegen.load_sidecar()
        assert sidecar["gramps_webapi_version"] == SCHEMA_VERSION

    def test_pin_matches_snapshot_info_version(self):
        """Snapshot info.version equals SCHEMA_VERSION."""
        spec = codegen.load_snapshot()
        assert spec["info"]["version"] == SCHEMA_VERSION

    def test_sidecar_sha256_matches_snapshot_bytes(self):
        """Sidecar sha256 covers the checked-in snapshot bytes."""
        sidecar = codegen.load_sidecar()
        digest = hashlib.sha256(codegen.SNAPSHOT_PATH.read_bytes()).hexdigest()
        assert sidecar["sha256"] == digest

    def test_sidecar_records_provenance(self):
        """Sidecar carries license, attribution and source fields."""
        sidecar = codegen.load_sidecar()
        assert sidecar["license"] == "AGPL-3.0-only"
        assert "gramps-web-api" in sidecar["attribution"]
        assert sidecar["person_schema_source"].endswith(
            f"v{SCHEMA_VERSION}/gramps_webapi/api/resources/schemas.py"
        )
        assert sidecar["source_url"].endswith("/api/openapi.json")
        assert sidecar["docker_image"].startswith("ghcr.io/gramps-project/grampsweb:")


class TestCheck:
    """`codegen --check` must pass on the checked-in table."""

    def test_checked_in_table_matches_codegen(self):
        """codegen --check finds no drift in the committed table."""
        drift = codegen.check()
        assert drift == "", drift

    def test_cli_check_exit_code(self):
        """CLI --check exits 0 when the table is current."""
        assert codegen.main(["--check"]) == 0

    def test_check_reports_drift(self, tmp_path):
        """check() returns a unified diff for a stale table."""
        stale = tmp_path / "resource_table.py"
        stale.write_text("# stale\n")
        drift = codegen.check(table_path=stale)
        assert "resource_table.py" in drift
        assert "+" in drift


class TestGeneratedTable:
    """Shape of the table that ships in the package."""

    def test_every_entity_has_a_row(self):
        """Every policy entity has a generated row."""
        from src.gramps_mcp.resource_table import ENTITY_RESOURCES

        assert tuple(ENTITY_RESOURCES) == ENTITY_NAMES
        for row in ENTITY_RESOURCES.values():
            assert isinstance(row, EntityResource)
            assert row.collection_verbs == ("GET", "POST")
            assert row.item_verbs == ("GET", "PUT", "DELETE")
            assert row.collection_path.endswith("/")
            assert row.item_path == row.collection_path + "{handle}"

    def test_read_only_fields_never_appear(self):
        """READ_ONLY_FIELDS are excluded from every row."""
        from src.gramps_mcp.resource_table import ENTITY_RESOURCES

        for row in ENTITY_RESOURCES.values():
            names = {field.name for field in row.fields}
            assert not names & set(READ_ONLY_FIELDS), row.entity

    def test_person_fields_follow_upstream_person_schema(self):
        """Person row fields equal PERSON_SCHEMA_FIELDS minus read-only ones."""
        from src.gramps_mcp.resource_table import ENTITY_RESOURCES

        expected = tuple(
            name for name in PERSON_SCHEMA_FIELDS if name not in READ_ONLY_FIELDS
        )
        assert tuple(f.name for f in ENTITY_RESOURCES["person"].fields) == expected

    def test_list_params_include_pagination(self):
        """List params carry page and pagesize."""
        from src.gramps_mcp.resource_table import ENTITY_RESOURCES

        names = {p.name for p in ENTITY_RESOURCES["event"].list_params}
        assert {"page", "pagesize", "gql", "gramps_id", "sort"} <= names

    def test_generated_file_is_short_and_marked(self):
        """Generated file stays under the limit and has the marker."""
        text = codegen.TABLE_PATH.read_text()
        lines = text.splitlines()
        assert len(lines) < 500
        assert "# SPDX-License-Identifier: AGPL-3.0-only" in lines[:5]
        assert codegen.GENERATED_MARKER in text


def _mini_spec(person_component: bool = True) -> dict:
    """A two-entity spec in the 3.16 shape, small enough to assert on."""
    schemas = {
        "Tag": {
            "type": "object",
            "properties": {
                "_class": {"type": "string"},
                "change": {"type": "number"},
                "color": {"type": "string"},
                "handle": {"type": "string"},
                "name": {"type": "string"},
                "priority": {"type": "integer"},
            },
        },
        "Event": {
            "type": "object",
            "properties": {
                "backlinks": {"allOf": [{"$ref": "#/components/schemas/Backlinks"}]},
                "citation_list": {"type": "array", "items": {"type": "string"}},
                "date": {"allOf": [{"$ref": "#/components/schemas/Date"}]},
                "extended": {"description": "no type"},
                "media_list": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/MediaReference"},
                },
                "type": {"type": "string"},
            },
        },
    }
    if person_component:
        schemas["Person"] = {
            "type": "object",
            "properties": {name: {"type": "string"} for name in PERSON_SCHEMA_FIELDS},
        }
    list_params = [
        {"name": "page", "in": "query", "schema": {"type": "integer"}},
        {"name": "gql", "in": "query", "schema": {"type": "string"}},
        {"name": "keys", "in": "query", "schema": {"type": "array"}},
    ]
    return {
        "openapi": "3.0.3",
        "info": {"version": "9.9.9"},
        "paths": {
            "/api/tags/": {
                "get": {"parameters": list_params},
                "post": {},
            },
            "/api/tags/{handle}": {"get": {}, "put": {}, "delete": {}},
            "/api/events/": {
                "get": {"parameters": list_params + [{"name": "dates", "in": "query"}]},
                "post": {},
            },
            "/api/events/{handle}": {"get": {}, "put": {}, "delete": {}},
            "/api/people/": {
                "get": {"parameters": list_params},
                "post": {},
            },
            "/api/people/{handle}": {"get": {}, "put": {}, "delete": {}},
        },
        "components": {"schemas": schemas},
    }


class TestBuildRows:
    """Codegen table-shape rules on a small fixture spec."""

    def test_rows_for_requested_entities(self):
        """build_rows keeps the requested entity order."""
        rows = codegen.build_rows(_mini_spec(), entities=("tag", "event"))
        assert tuple(rows) == ("tag", "event")
        tag = rows["tag"]
        assert tag == EntityResource(
            entity="tag",
            component="Tag",
            collection_path="tags/",
            item_path="tags/{handle}",
            collection_verbs=("GET", "POST"),
            item_verbs=("GET", "PUT", "DELETE"),
            list_params=(
                ListParam("page", "integer"),
                ListParam("gql", "string"),
                ListParam("keys", "array"),
            ),
            fields=(
                FieldSpec("color", "string"),
                FieldSpec("name", "string"),
                FieldSpec("priority", "integer"),
            ),
        )

    def test_field_types_resolve_refs_arrays_and_untyped(self):
        """Type rendering handles refs, arrays and untyped fields."""
        rows = codegen.build_rows(_mini_spec(), entities=("event",))
        assert rows["event"].fields == (
            FieldSpec("citation_list", "array[string]"),
            FieldSpec("date", "Date"),
            FieldSpec("media_list", "array[MediaReference]"),
            FieldSpec("type", "string"),
        )
        assert rows["event"].list_params[-1] == ListParam("dates", "any")

    def test_person_without_component_uses_upstream_field_list(self):
        """Person falls back to PERSON_SCHEMA_FIELDS without a component."""
        rows = codegen.build_rows(
            _mini_spec(person_component=False), entities=("person",)
        )
        names = tuple(f.name for f in rows["person"].fields)
        assert names == tuple(
            n for n in PERSON_SCHEMA_FIELDS if n not in READ_ONLY_FIELDS
        )
        assert all(f.type == "any" for f in rows["person"].fields)

    def test_person_component_disagreeing_with_upstream_list_fails(self):
        """A Person component that disagrees with the list is an error."""
        spec = _mini_spec()
        spec["components"]["schemas"]["Person"]["properties"]["brand_new"] = {
            "type": "string"
        }
        with pytest.raises(codegen.CodegenError, match="brand_new"):
            codegen.build_rows(spec, entities=("person",))

    def test_missing_component_is_an_error(self):
        """A missing component schema raises CodegenError."""
        spec = _mini_spec()
        del spec["components"]["schemas"]["Tag"]
        with pytest.raises(codegen.CodegenError, match="Tag"):
            codegen.build_rows(spec, entities=("tag",))

    def test_missing_path_is_an_error(self):
        """A missing item path raises CodegenError."""
        spec = _mini_spec()
        del spec["paths"]["/api/tags/{handle}"]
        with pytest.raises(codegen.CodegenError, match="tags/{handle}"):
            codegen.build_rows(spec, entities=("tag",))

    def test_render_is_deterministic_and_dedupes_param_sets(self):
        """render is stable and shares identical param tuples."""
        spec = _mini_spec()
        rows = codegen.build_rows(spec, entities=("tag", "person"))
        text = codegen.render(rows)
        assert text == codegen.render(rows)
        # tag and person share one list-param set: it is emitted once.
        assert text.count('ListParam("page", "integer")') == 1
        # The generated module uses a relative import, so exec it as if it
        # lived in the package.
        namespace: dict = {"__package__": "src.gramps_mcp"}
        exec(compile(text, "<generated>", "exec"), namespace)
        assert tuple(namespace["ENTITY_RESOURCES"]) == ("tag", "person")

    def test_policy_maps_cover_every_entity(self):
        """Policy maps cover every entity and include handle."""
        assert tuple(ENTITY_COMPONENTS) == ENTITY_NAMES
        assert "handle" in READ_ONLY_FIELDS
        assert "change" in READ_ONLY_FIELDS
        assert "backlinks" in READ_ONLY_FIELDS

    def test_sidecar_round_trip(self):
        """build_sidecar records every provenance key."""
        sidecar = codegen.build_sidecar(
            spec_bytes=b"{}",
            source_url="http://x/api/openapi.json",
            docker_image="ghcr.io/gramps-project/grampsweb:1@sha256:abc",
            metadata={
                "gramps_webapi": {"version": "9.9.9"},
                "gramps": {"version": "6"},
            },
            openapi_version="3.0.3",
            fetched_on="2026-01-01",
        )
        assert sidecar["sha256"] == hashlib.sha256(b"{}").hexdigest()
        assert sidecar["gramps_webapi_version"] == "9.9.9"
        assert sidecar["gramps_version"] == "6"
        assert json.loads(json.dumps(sidecar)) == sidecar


class TestFieldAdditions:
    """Policy-supplied fields the stale snapshot components omit (#102)."""

    def test_additions_merge_sorted_into_row(self):
        """An addition joins the component fields in name order."""
        rows = codegen.build_rows(
            _mini_spec(),
            entities=("tag",),
            additions={"tag": (FieldSpec("comment", "string"),)},
        )
        assert rows["tag"].fields == (
            FieldSpec("color", "string"),
            FieldSpec("comment", "string"),
            FieldSpec("name", "string"),
            FieldSpec("priority", "integer"),
        )

    def test_addition_already_in_component_fails(self):
        """An addition the snapshot now declares must be dropped from policy."""
        with pytest.raises(codegen.CodegenError, match="tag.name"):
            codegen.build_rows(
                _mini_spec(),
                entities=("tag",),
                additions={"tag": (FieldSpec("name", "string"),)},
            )

    def test_read_only_addition_fails(self):
        """A read-only field cannot be added back as writable."""
        with pytest.raises(codegen.CodegenError, match="read-only"):
            codegen.build_rows(
                _mini_spec(),
                entities=("tag",),
                additions={"tag": (FieldSpec("change", "integer"),)},
            )

    def test_policy_additions_reach_generated_table(self):
        """Every FIELD_ADDITIONS entry is a field of the checked-in table."""
        from src.gramps_mcp.resource_policy import FIELD_ADDITIONS
        from src.gramps_mcp.resource_table import ENTITY_RESOURCES

        assert {
            entity: [spec in ENTITY_RESOURCES[entity].fields for spec in specs]
            for entity, specs in FIELD_ADDITIONS.items()
        } == {entity: [True] * len(specs) for entity, specs in FIELD_ADDITIONS.items()}
