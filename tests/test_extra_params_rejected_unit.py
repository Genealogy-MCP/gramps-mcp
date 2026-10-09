# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for unknown-key rejection on the parameter models (#71, #95).

Pydantic's default extra="ignore" turned a misspelled parameter into a silent
data loss: upsert_event(attributes=[...]) reported success and wrote nothing,
and search(page_size=5) returned a default page with nothing saying the limit
was dropped. Every parameter model an LLM fills in now forbids extra keys, and
the resulting error names the offending key and its nearest real field.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.analysis_params import (
    AncestorsParams,
    DescendantsParams,
    TreeInfoParams,
)
from src.gramps_mcp.models.parameters.base_params import (
    BaseGetMultipleParams,
    BaseGetSingleParams,
)
from src.gramps_mcp.models.parameters.citation_params import CitationData
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.media_params import (
    MediaDownloadParams,
    MediaSaveParams,
)
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.people_params import PersonData
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams
from src.gramps_mcp.models.parameters.repository_params import RepositoryData
from src.gramps_mcp.models.parameters.simple_params import (
    DeleteParams,
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
)
from src.gramps_mcp.models.parameters.source_params import SourceSaveParams
from src.gramps_mcp.models.parameters.tag_params import TagSaveParams, TagSearchParams
from src.gramps_mcp.models.parameters.transactions_params import (
    TransactionHistoryParams,
)
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

# Read and delete models (#95). Each one parses a command an LLM wrote, so it
# sits on the same side of the trust boundary as the write models above.
READ_MODELS = [
    AncestorsParams,
    BaseGetMultipleParams,
    BaseGetSingleParams,
    DeleteParams,
    DescendantsParams,
    MediaDownloadParams,
    SimpleFindParams,
    SimpleGetParams,
    SimpleSearchParams,
    TagSearchParams,
    TransactionHistoryParams,
    TreeInfoParams,
]

ALL_MODELS = WRITE_MODELS + READ_MODELS


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__name__)
def test_unknown_key_is_rejected(model):
    """Every parameter model refuses a key it does not declare."""
    with pytest.raises(ValidationError) as excinfo:
        model(definitely_not_a_field=1)

    assert "definitely_not_a_field" in str(excinfo.value)


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__name__)
def test_no_model_silently_ignores_extras(model):
    """The config is set on every model, not only the ones tested above."""
    assert model.model_config.get("extra") == "forbid"


def test_the_reported_read_typo_is_rejected():
    """The exact call from #95 now fails instead of returning a default page."""
    with pytest.raises(ValidationError) as excinfo:
        BaseGetMultipleParams(page_size=5)

    message = describe_validation_error(excinfo.value, BaseGetMultipleParams)

    assert "page_size" in message
    assert "pagesize" in message


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


def _registry_schemas():
    """Every params_schema wired into the operation registry, by operation."""
    from src.gramps_mcp.operations import OPERATION_REGISTRY

    return sorted(
        ((name, entry.params_schema) for name, entry in OPERATION_REGISTRY.items()),
        key=lambda pair: pair[0],
    )


@pytest.mark.parametrize(
    ("operation", "schema"), _registry_schemas(), ids=lambda v: str(v)
)
def test_every_registered_schema_forbids_extra(operation, schema):
    """A model wired into the registry forbids extra keys.

    The hand-kept model lists above miss a model that is added later; the
    registry is the source of truth for what an LLM can call, so a schema
    that still uses extra="ignore" fails here regardless of the lists.
    """
    assert schema.model_config.get("extra") == "forbid", (
        f"{operation} uses {schema.__name__} without extra='forbid'"
    )
