"""
Unit tests for models/api_mapping.py — parameter model lookup and validation.
"""

import pytest
from pydantic import BaseModel

from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.api_mapping import (
    get_param_model,
    validate_api_call_params,
)


class TestGetParamModel:
    """Test get_param_model lookup."""

    def test_known_call_with_params(self):
        model = get_param_model(ApiCalls.GET_PEOPLE)
        assert model is not None
        assert issubclass(model, BaseModel)

    def test_known_call_no_params(self):
        model = get_param_model(ApiCalls.DELETE_PERSON)
        assert model is None

    def test_trees_no_params(self):
        model = get_param_model(ApiCalls.GET_TREES)
        assert model is None


class TestValidateApiCallParams:
    """Test validate_api_call_params validation."""

    def test_valid_params(self):
        result = validate_api_call_params(
            ApiCalls.GET_PEOPLE, {"pagesize": 10, "page": 1}
        )
        assert result is not None
        assert hasattr(result, "pagesize")

    def test_no_param_call_with_params_raises(self):
        with pytest.raises(ValueError, match="does not accept parameters"):
            validate_api_call_params(ApiCalls.DELETE_PERSON, {"extra": "bad"})

    def test_no_param_call_no_params(self):
        result = validate_api_call_params(ApiCalls.DELETE_PERSON, {})
        assert result is None

    def test_invalid_params_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            validate_api_call_params(
                ApiCalls.GET_SOURCES, {"sort": "nonexistent_field"}
            )
