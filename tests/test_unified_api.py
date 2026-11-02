"""
Tests for the unified API call system.

This module tests pagination constraints on the params models, URL
building, and the unified make_api_call method against the real API.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.client import GrampsWebAPIClient
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.base_params import (
    BaseGetMultipleParams,
    BaseGetSingleParams,
)
from src.gramps_mcp.models.parameters.search_params import SearchParams
from src.gramps_mcp.models.parameters.transactions_params import (
    TransactionHistoryParams,
)


class TestPaginationConstraints:
    """Verify all pagination models reject page=0 (API 3.x is 1-based)."""

    def test_search_params_page_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            SearchParams(query="test", page=0)

    def test_search_params_page_one_accepted(self):
        params = SearchParams(query="test", page=1)
        assert params.page == 1

    def test_transaction_history_params_page_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            TransactionHistoryParams(page=0)

    def test_transaction_history_params_page_one_accepted(self):
        params = TransactionHistoryParams(page=1)
        assert params.page == 1

    def test_base_get_multiple_page_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            BaseGetMultipleParams(page=0)

    def test_base_get_multiple_page_negative_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            BaseGetMultipleParams(page=-1)

    def test_base_get_multiple_page_one_accepted(self):
        assert BaseGetMultipleParams(page=1).page == 1


class TestUrlBuilding:
    """Test URL building logic — pure string manipulation, no API calls."""

    def test_build_url_with_substitution(self):
        """Test URL building with parameter substitution."""
        client = GrampsWebAPIClient()

        url = client._build_url_with_substitution(
            tree_id="test_tree",
            endpoint="people/{handle}/timeline",
            url_params={"handle": "test_handle_123"},
        )

        assert "test_handle_123" in url
        assert "{handle}" not in url
        assert url.endswith("people/test_handle_123/timeline")

    def test_build_url_with_substitution_multiple_params(self):
        """Test URL building with multiple parameter substitutions."""
        client = GrampsWebAPIClient()

        url = client._build_url_with_substitution(
            tree_id="test_tree",
            endpoint="relations/{handle1}/{handle2}",
            url_params={"handle1": "person1", "handle2": "person2"},
        )

        assert "person1" in url
        assert "person2" in url
        assert "{handle1}" not in url
        assert "{handle2}" not in url
        assert url.endswith("relations/person1/person2")

    def test_build_url_with_substitution_missing_params(self):
        """Test URL building with missing parameters."""
        client = GrampsWebAPIClient()

        with pytest.raises(ValueError, match="Missing required URL parameters"):
            client._build_url_with_substitution(
                tree_id="test_tree",
                endpoint="people/{handle}/timeline",
                url_params={},
            )


@pytest.mark.integration
class TestUnifiedApiCall:
    """Test the unified API call functionality with real API integration."""

    @pytest.fixture
    async def client(self):
        """Create a real GrampsWebAPIClient for integration testing."""
        client = GrampsWebAPIClient()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_make_api_call_parameter_validation(self, client):
        """Test parameter validation in make_api_call."""
        # Test with valid parameters
        params = BaseGetMultipleParams(page=1, pagesize=10)

        # This should not raise an error during parameter validation
        # (it may fail during actual HTTP call if no server is available)
        try:
            await client.make_api_call(
                ApiCalls.GET_PEOPLE,
                params=BaseGetMultipleParams.model_validate(params),
                tree_id="default",
            )
        except Exception as e:
            # We expect network errors, but not parameter validation errors
            assert "Missing required URL parameters" not in str(e)
            assert "ValidationError" not in str(e)

    @pytest.mark.asyncio
    async def test_make_api_call_url_substitution_validation(self, client):
        """Test URL parameter substitution validation."""
        # Test that missing URL parameters are caught
        with pytest.raises(ValueError, match="Missing required URL parameters"):
            await client.make_api_call(
                ApiCalls.GET_PERSON,  # Requires {handle}
                params=BaseGetSingleParams(strip=True),
                tree_id="default",
                # Missing handle parameter
            )

    @pytest.mark.asyncio
    async def test_make_api_call_with_pydantic_params(self, client):
        """Test make_api_call with Pydantic model parameters."""
        params = BaseGetMultipleParams(page=2, pagesize=10)

        try:
            await client.make_api_call(
                ApiCalls.GET_PEOPLE,
                params=BaseGetMultipleParams.model_validate(params),
                tree_id="default",
            )
        except Exception as e:
            # We expect network errors, but parameter validation should work
            assert "ValidationError" not in str(e)
            assert "Missing required URL parameters" not in str(e)
