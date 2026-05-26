# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Tests for BaseDataModel.to_api_payload() default and client dispatch."""

from src.gramps_mcp.models.parameters.base_params import BaseDataModel
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams


class TestBaseDataModelToApiPayload:
    """BaseDataModel.to_api_payload() returns model_dump(exclude_none=True)."""

    def test_base_data_model_has_to_api_payload(self) -> None:
        """BaseDataModel instances expose to_api_payload()."""
        model = BaseDataModel(gramps_id="I0001", private=True)
        result = model.to_api_payload()
        assert result == {"gramps_id": "I0001", "private": True, "list_mode": "merge"}

    def test_subclass_without_override_uses_base_default(self) -> None:
        """FamilySaveParams (no override) inherits to_api_payload() from base."""
        model = FamilySaveParams(father_handle="abc123", private=False)
        result = model.to_api_payload()
        assert result == {
            "father_handle": "abc123",
            "private": False,
            "list_mode": "merge",
        }

    def test_note_save_params_calls_super_to_api_payload(self) -> None:
        """NoteSaveParams.to_api_payload() wraps text in StyledText via override."""
        model = NoteSaveParams(text="Hello world", type="General")
        result = model.to_api_payload()
        assert result["text"] == {
            "_class": "StyledText",
            "string": "Hello world",
        }
        assert result["type"] == "General"

    def test_note_save_params_inherits_base_data_model(self) -> None:
        """NoteSaveParams is a BaseDataModel subclass."""
        assert issubclass(NoteSaveParams, BaseDataModel)

    def test_none_fields_excluded_from_payload(self) -> None:
        """to_api_payload() excludes None fields."""
        model = FamilySaveParams(father_handle="abc123")
        result = model.to_api_payload()
        assert "mother_handle" not in result
        assert "child_handles" not in result
        assert result["father_handle"] == "abc123"

    def test_client_dispatch_no_getattr(self) -> None:
        """client.py no longer uses getattr for to_api_payload dispatch."""
        import inspect

        from src.gramps_mcp.client import GrampsWebAPIClient

        source = inspect.getsource(GrampsWebAPIClient.make_api_call)
        assert "getattr" not in source, "client.py should not use getattr dispatch"
