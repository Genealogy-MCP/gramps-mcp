# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for unknown-key rejection on the upsert parameter models (#71).

Pydantic's default extra="ignore" turned a misspelled parameter into a silent
data loss: upsert_event(attributes=[...]) reported success and wrote nothing.
Every write model now forbids extra keys, and the resulting error names the
offending key and its nearest real field.
"""

import pytest
from pydantic import ValidationError

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
from src.gramps_mcp.tools._errors import (
    McpToolError,
    describe_validation_error,
    parse_params,
)

WRITE_MODELS = [
    CitationData,
    EventSaveParams,
    FamilySaveParams,
    MediaSaveParams,
    NoteSaveParams,
    PersonData,
    PlaceSaveParams,
    RepositoryData,
    SourceSaveParams,
    TagSaveParams,
]


@pytest.mark.parametrize("model", WRITE_MODELS, ids=lambda m: m.__name__)
def test_unknown_key_is_rejected(model):
    """Every write model refuses a key it does not declare."""
    with pytest.raises(ValidationError) as excinfo:
        model(definitely_not_a_field=1)

    assert "definitely_not_a_field" in str(excinfo.value)


@pytest.mark.parametrize("model", WRITE_MODELS, ids=lambda m: m.__name__)
def test_no_write_model_silently_ignores_extras(model):
    """The config is set on every write model, not only the ones tested above."""
    assert model.model_config.get("extra") == "forbid"


def test_the_reported_typo_is_rejected():
    """The exact call from #71 now fails instead of reporting success."""
    with pytest.raises(ValidationError):
        EventSaveParams(handle="abc123", attributes=[{"type": "Vessel", "value": "X"}])


def test_known_keys_still_accepted():
    """Forbidding extras does not disturb a well-formed payload."""
    params = EventSaveParams(
        handle="abc123",
        attribute_list=[{"type": "Vessel", "value": "X"}],
    )

    assert params.to_api_payload() == {
        "handle": "abc123",
        "attribute_list": [{"type": "Vessel", "value": "X"}],
        "list_mode": "merge",
    }


class TestDescribeValidationError:
    """The message an LLM receives has to name the fix, not just the failure."""

    def test_names_the_key_and_suggests_the_real_field(self):
        with pytest.raises(ValidationError) as excinfo:
            EventSaveParams(attributes=[])

        message = describe_validation_error(excinfo.value, EventSaveParams)

        assert "attributes" in message
        assert "attribute_list" in message

    def test_omits_a_suggestion_when_nothing_is_close(self):
        with pytest.raises(ValidationError) as excinfo:
            EventSaveParams(zzzzzzzz=1)

        message = describe_validation_error(excinfo.value, EventSaveParams)

        assert "zzzzzzzz" in message
        assert "did you mean" not in message.lower()

    def test_reports_every_unknown_key_at_once(self):
        with pytest.raises(ValidationError) as excinfo:
            EventSaveParams(attributes=[], notes=[])

        message = describe_validation_error(excinfo.value, EventSaveParams)

        assert "attributes" in message
        assert "notes" in message

    def test_falls_back_to_pydantic_for_other_validation_errors(self):
        """A wrong type is not an unknown key and keeps its original detail."""
        with pytest.raises(ValidationError) as excinfo:
            NoteSaveParams(text="ok", format=7)

        message = describe_validation_error(excinfo.value, NoteSaveParams)

        assert "format" in message
        assert "not permitted" not in message


class TestParseParams:
    """The shared parse boundary every upsert tool goes through."""

    def test_returns_the_validated_model_on_good_input(self):
        params = parse_params(EventSaveParams, {"handle": "abc123"})

        assert params.handle == "abc123"

    def test_raises_mcp_tool_error_naming_the_near_miss(self):
        with pytest.raises(McpToolError) as excinfo:
            parse_params(EventSaveParams, {"attributes": []})

        message = str(excinfo.value)
        assert "attributes" in message
        assert "attribute_list" in message
