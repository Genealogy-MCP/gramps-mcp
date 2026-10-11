# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Write-model drift against the generated resource table (#102).

The hand models stay the parse boundary for every upsert, so nothing
filters a payload against the table at runtime. These tests are the
other half of that contract: every writable field a hand model declares
must be a field the table lists for its entity, or a payload-only field
named in ``overlays.PAYLOAD_ONLY_FIELDS`` that the model's payload hook
consumes before the request is sent. No Docker needed.
"""

import warnings

import pytest

from src.gramps_mcp.client import api_body
from src.gramps_mcp.models.parameters.citation_params import CitationData
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.media_params import MediaSaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.people_params import PersonData
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams
from src.gramps_mcp.models.parameters.repository_params import RepositoryData
from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
from src.gramps_mcp.models.parameters.tag_params import TagSaveParams
from src.gramps_mcp.overlays import PAYLOAD_ONLY_FIELDS, ROUTING_FIELDS
from src.gramps_mcp.resource_policy import READ_ONLY_FIELDS
from src.gramps_mcp.resource_table import ENTITY_RESOURCES

# All ten write models, keyed by the entity whose table row they write.
WRITE_MODELS = {
    "person": PersonData,
    "family": FamilySaveParams,
    "event": EventSaveParams,
    "place": PlaceSaveParams,
    "source": SourceSaveParams,
    "citation": CitationData,
    "note": NoteSaveParams,
    "repository": RepositoryData,
    "media": MediaSaveParams,
    "tag": TagSaveParams,
}

# A value each payload-only field accepts, used to prove the hook drops it.
_SAMPLE_VALUES = {
    "list_mode": "replace",
    "enclosed_by": "parent_handle",
    "child_handles": ["child_handle"],
    "family_type": "Married",
    "file_location": "/nonexistent/upload.jpg",
}


def _table_fields(entity):
    """
    Return the writable field names the table lists for an entity.

    Args:
        entity (str): Entity key.

    Returns:
        set[str]: Field names of the row.
    """
    return {spec.name for spec in ENTITY_RESOURCES[entity].fields}


def _model_fields(model):
    """
    Return the writable fields a hand model declares, routing key excluded.

    Args:
        model (type): Pydantic write model.

    Returns:
        set[str]: Field names a caller may send in the body.
    """
    return set(model.model_fields) - set(ROUTING_FIELDS)


def drift(entity, model):
    """
    Compare one hand model with its table row.

    Args:
        entity (str): Entity key.
        model (type): Pydantic write model for that entity.

    Returns:
        tuple[list[str], list[str]]: (errors, warnings). Errors are model
            fields the table does not list and the allowlist does not
            cover, plus read-only fields; warnings are table fields the
            model does not expose.
    """
    table = _table_fields(entity)
    fields = _model_fields(model)
    allowed = {f for (m, f) in PAYLOAD_ONLY_FIELDS if m is model}
    errors = [
        f"{model.__name__}.{name} is not a {entity} table field"
        for name in sorted(fields - table - allowed)
    ]
    errors += [
        f"{model.__name__}.{name} is read-only"
        for name in sorted(fields & set(READ_ONLY_FIELDS))
    ]
    missing = [
        f"{model.__name__} does not expose {entity}.{name}"
        for name in sorted(table - fields)
    ]
    return errors, missing


class TestWriteModelDrift:
    """Every write model matches its generated table row."""

    def test_covers_all_ten_write_models(self):
        """The drift check runs over every entity in the table."""
        assert sorted(WRITE_MODELS) == sorted(ENTITY_RESOURCES)

    @pytest.mark.parametrize("entity", sorted(WRITE_MODELS))
    def test_model_fields_in_table(self, entity):
        """A field outside the table fails unless allowlisted and consumed."""
        errors, missing = drift(entity, WRITE_MODELS[entity])
        for message in missing:
            warnings.warn(message, stacklevel=1)
        assert errors == []

    def test_known_gaps_are_warnings(self):
        """Table fields the models lack today are reported, not failed.

        Reason: the gaps are a subset check, not an exact pin, so a field the
        next snapshot adds only warns instead of failing CI (#99 US4).
        """
        found = {
            message
            for entity, model in WRITE_MODELS.items()
            for message in drift(entity, model)[1]
        }
        known = {
            "FamilySaveParams does not expose family.lds_ord_list",
            "FamilySaveParams does not expose family.type",
            "PlaceSaveParams does not expose place.title",
        }
        assert known - found == set()

    def test_detects_unknown_field(self):
        """A model field the table does not list is an error."""
        from pydantic import BaseModel

        class Stray(BaseModel):
            name: str = ""
            not_in_table: str = ""

        assert drift("tag", Stray)[0] == ["Stray.not_in_table is not a tag table field"]

    def test_detects_read_only_field(self):
        """A read-only field on a model is an error even if the table lists it."""
        from pydantic import BaseModel

        class Stamped(BaseModel):
            name: str = ""
            change: int = 0

        assert drift("tag", Stamped)[0] == [
            "Stamped.change is not a tag table field",
            "Stamped.change is read-only",
        ]

    def test_routing_key_is_handle_only(self):
        """Only the item-path placeholder is exempt from the field checks."""
        assert ROUTING_FIELDS == ("handle",)


class TestPayloadOnlyAllowlist:
    """Each allowlist entry is consumed by its model's payload hook."""

    def test_expected_entries(self):
        """The allowlist names exactly the known payload-only fields."""
        assert sorted((m.__name__, f) for (m, f) in PAYLOAD_ONLY_FIELDS) == sorted(
            # Reason: tags have no list fields, so TagSaveParams has no list_mode.
            [
                (m.__name__, "list_mode")
                for m in WRITE_MODELS.values()
                if m is not TagSaveParams
            ]
            + [("PlaceSaveParams", "enclosed_by")]
            + [("FamilySaveParams", "child_handles")]
            + [("FamilySaveParams", "family_type")]
            + [("MediaSaveParams", "file_location")]
        )

    @pytest.mark.parametrize(
        "model,field",
        sorted(PAYLOAD_ONLY_FIELDS, key=lambda e: (e[0].__name__, e[1])),
        ids=lambda v: v.__name__ if isinstance(v, type) else v,
    )
    def test_entry_is_consumed(self, model, field):
        """The field never reaches the request body the client sends."""
        params = model(handle="h1", **{field: _SAMPLE_VALUES[field]})
        body, _ = api_body(params)
        assert field not in body

    @pytest.mark.parametrize(
        "model,field",
        sorted(PAYLOAD_ONLY_FIELDS, key=lambda e: (e[0].__name__, e[1])),
        ids=lambda v: v.__name__ if isinstance(v, type) else v,
    )
    def test_entry_is_declared(self, model, field):
        """An allowlist entry names a field its model actually declares."""
        assert field in model.model_fields

    def test_list_mode_returned_separately(self):
        """api_body hands list_mode to the merge step instead of the body."""
        params = EventSaveParams(handle="h1", list_mode="replace")
        assert api_body(params) == ({"handle": "h1"}, "replace")


class TestDroppedFields:
    """Fields the server never stores are not accepted (#102)."""

    def test_media_rejects_media_list(self):
        """Gramps media records hold no media_list; the field was dropped."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MediaSaveParams(handle="h1", media_list=[{"ref": "m"}])

    @pytest.mark.parametrize("entity", sorted(WRITE_MODELS))
    def test_no_change_field(self, entity):
        """change is server-set, so no write model declares it."""
        assert "change" not in WRITE_MODELS[entity].model_fields
