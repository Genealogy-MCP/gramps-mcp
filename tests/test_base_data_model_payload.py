# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Tests for BaseDataModel.to_api_payload() default and client dispatch."""

from src.gramps_mcp.models.parameters.base_params import BaseDataModel
from src.gramps_mcp.models.parameters.family_params import FamilySaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.place_params import PlaceSaveParams


class TestBaseDataModelToApiPayload:
    """BaseDataModel.to_api_payload() returns model_dump(exclude_none=True)."""

    def test_base_data_model_has_to_api_payload(self) -> None:
        """BaseDataModel instances expose to_api_payload()."""
        model = BaseDataModel(gramps_id="I0001", private=True)
        result = model.to_api_payload()
        assert result == {"gramps_id": "I0001", "private": True, "list_mode": "merge"}

    def test_subclass_with_override_calls_super(self) -> None:
        """FamilySaveParams.to_api_payload() delegates to super() for base fields."""
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

    def test_place_save_params_inherits_base_data_model(self) -> None:
        """PlaceSaveParams is a BaseDataModel subclass, so client.py dispatches
        to to_api_payload() instead of raw model_dump()."""
        assert issubclass(PlaceSaveParams, BaseDataModel)

    def test_place_save_params_wraps_alt_names(self) -> None:
        """alt_names strings become PlaceName objects the Gramps API accepts."""
        model = PlaceSaveParams(
            name={"value": "Piedimonte Matese"},
            place_type="City",
            alt_names=["Piedimonte d'Alife"],
        )
        result = model.to_api_payload()
        assert result["alt_names"] == [{"value": "Piedimonte d'Alife"}]

    def test_place_save_params_alt_names_omitted_when_unset(self) -> None:
        """No alt_names means no alt_names key in the payload."""
        model = PlaceSaveParams(name={"value": "Napoli"}, place_type="City")
        assert "alt_names" not in model.to_api_payload()

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
