"""
Unit tests for client.py — pure functions, HTTP error formatting,
URL building, and _make_request branching logic.

Tests mock auth_manager.client.request or _make_request to avoid
network calls. Existing merge-logic tests live in test_client_merge.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.gramps_mcp.client import (
    GrampsAPIError,
    GrampsWebAPIClient,
    _normalise_url_keys,
)
from src.gramps_mcp.media_client import MediaClient
from src.gramps_mcp.models.api_calls import ApiCalls

# ---------------------------------------------------------------------------
# _normalise_url_keys  (pure function)
# ---------------------------------------------------------------------------


class TestNormaliseUrlKeys:
    """Test _normalise_url_keys in-place mutation."""

    def test_no_urls_key(self):
        data = {"name": "test"}
        _normalise_url_keys(data)
        assert data == {"name": "test"}

    def test_empty_urls_list(self):
        data = {"urls": []}
        _normalise_url_keys(data)
        assert data == {"urls": []}

    def test_description_renamed_to_desc(self):
        data = {"urls": [{"path": "https://x.com", "description": "Main"}]}
        _normalise_url_keys(data)
        assert data["urls"][0]["desc"] == "Main"
        assert "description" not in data["urls"][0]

    def test_desc_already_present(self):
        data = {"urls": [{"desc": "Keep me", "description": "Ignore"}]}
        _normalise_url_keys(data)
        assert data["urls"][0]["desc"] == "Keep me"
        assert "description" in data["urls"][0]

    def test_only_desc_no_change(self):
        data = {"urls": [{"desc": "OK"}]}
        _normalise_url_keys(data)
        assert data["urls"][0] == {"desc": "OK"}

    def test_non_dict_url_entry_skipped(self):
        data = {"urls": ["not-a-dict", {"description": "X"}]}
        _normalise_url_keys(data)
        assert data["urls"][0] == "not-a-dict"
        assert data["urls"][1]["desc"] == "X"

    def test_none_urls_is_noop(self):
        """urls=None should be treated as falsy (no-op)."""
        data = {"urls": None}
        _normalise_url_keys(data)
        assert data == {"urls": None}


# ---------------------------------------------------------------------------
# _format_http_error
# ---------------------------------------------------------------------------


def _make_http_status_error(
    status_code: int, url: str = "http://localhost/api/people/abc"
) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError with the given status code and URL."""
    request = httpx.Request("GET", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        message=f"HTTP {status_code}", request=request, response=response
    )


class TestFormatHttpError:
    """Test _format_http_error for each status code branch."""

    def _client(self) -> GrampsWebAPIClient:
        client = GrampsWebAPIClient()
        return client

    def test_401(self):
        client = self._client()
        err = _make_http_status_error(401)
        result = client._format_http_error(err)
        assert "Authentication failed" in result

    def test_403(self):
        client = self._client()
        err = _make_http_status_error(403)
        result = client._format_http_error(err)
        assert "Permission denied" in result

    def test_404(self):
        client = self._client()
        err = _make_http_status_error(404)
        result = client._format_http_error(err)
        assert "not found" in result

    def test_422(self):
        client = self._client()
        err = _make_http_status_error(422)
        result = client._format_http_error(err)
        assert "Invalid data" in result

    def test_500(self):
        client = self._client()
        err = _make_http_status_error(500)
        result = client._format_http_error(err)
        assert "Server error" in result

    def test_502(self):
        client = self._client()
        err = _make_http_status_error(502)
        result = client._format_http_error(err)
        assert "Server error" in result

    def test_418_other(self):
        client = self._client()
        err = _make_http_status_error(418)
        result = client._format_http_error(err)
        assert "status 418" in result

    def test_url_prefix_stripped(self):
        client = self._client()
        full_url = f"{client.base_url}/people/abc"
        err = _make_http_status_error(404, url=full_url)
        result = client._format_http_error(err)
        assert client.base_url not in result
        assert "/people/abc" in result


# ---------------------------------------------------------------------------
# _build_url_with_substitution
# ---------------------------------------------------------------------------


class TestBuildUrlWithSubstitution:
    """Test URL building with parameter substitution."""

    def _client(self) -> GrampsWebAPIClient:
        return GrampsWebAPIClient()

    def test_single_placeholder(self):
        client = self._client()
        url = client._build_url_with_substitution(
            "t1", "people/{handle}", {"handle": "abc123"}
        )
        assert url.endswith("/people/abc123")

    def test_multiple_placeholders(self):
        client = self._client()
        url = client._build_url_with_substitution(
            "t1",
            "events/{handle1}/span/{handle2}",
            {"handle1": "e1", "handle2": "e2"},
        )
        assert "/events/e1/span/e2" in url

    def test_missing_placeholder_raises(self):
        client = self._client()
        with pytest.raises(ValueError, match="Missing required URL parameters"):
            client._build_url_with_substitution("t1", "people/{handle}", {})

    def test_tree_id_placeholder(self):
        client = self._client()
        url = client._build_url_with_substitution(
            "t1", "trees/{tree_id}", {"tree_id": "my-tree"}
        )
        assert "/trees/my-tree" in url


# ---------------------------------------------------------------------------
# _make_request
# ---------------------------------------------------------------------------


class TestMakeRequest:
    """Test _make_request error handling and retry logic."""

    def _setup_client(self) -> GrampsWebAPIClient:
        client = GrampsWebAPIClient()
        client.auth_manager = MagicMock()
        client.auth_manager.get_token = AsyncMock()
        client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        client.auth_manager.authenticate = AsyncMock()
        client.auth_manager.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_401_with_retry(self):
        """401 + retry_auth=True retries after re-auth."""
        client = self._setup_client()

        resp_401 = MagicMock()
        resp_401.status_code = 401

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.text = '{"ok": true}'
        resp_200.json.return_value = {"ok": True}
        resp_200.raise_for_status = MagicMock()

        mock_request = AsyncMock(side_effect=[resp_401, resp_200])
        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = mock_request

        result = await client._make_request("GET", "http://test/api/people/")
        assert result == {"ok": True}
        client.auth_manager.authenticate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_401_no_retry(self):
        """401 + retry_auth=False raises GrampsAPIError."""
        client = self._setup_client()

        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "401",
                request=httpx.Request("GET", "http://test/api/people/"),
                response=httpx.Response(401),
            )
        )

        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(return_value=resp_401)

        with pytest.raises(GrampsAPIError, match="Authentication failed"):
            await client._make_request(
                "GET", "http://test/api/people/", retry_auth=False
            )

    @pytest.mark.asyncio
    async def test_empty_response_body(self):
        """Empty response returns {}."""
        client = self._setup_client()

        resp = MagicMock()
        resp.status_code = 200
        resp.text = "  "
        resp.raise_for_status = MagicMock()

        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(return_value=resp)

        result = await client._make_request("GET", "http://test/api/people/")
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_response_with_headers(self):
        """Empty response + return_headers returns ({}, headers)."""
        client = self._setup_client()

        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        resp.headers = {"x-total-count": "0"}
        resp.raise_for_status = MagicMock()

        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(return_value=resp)

        result = await client._make_request(
            "GET", "http://test/api/search/", return_headers=True
        )
        assert result == ({}, {"x-total-count": "0"})

    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Invalid JSON returns error dict with raw_content."""
        client = self._setup_client()

        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<html>not json</html>"
        resp.raise_for_status = MagicMock()
        resp.json.side_effect = ValueError("Expecting JSON")

        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(return_value=resp)

        result = await client._make_request("GET", "http://test/api/reports/")
        assert "raw_content" in result
        assert result["raw_content"] == "<html>not json</html>"

    @pytest.mark.asyncio
    async def test_invalid_json_with_headers(self):
        """Invalid JSON + return_headers returns (error_dict, headers)."""
        client = self._setup_client()

        resp = MagicMock()
        resp.status_code = 200
        resp.text = "broken"
        resp.headers = {"content-type": "text/html"}
        resp.raise_for_status = MagicMock()
        resp.json.side_effect = ValueError("bad json")

        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(return_value=resp)

        data, headers = await client._make_request(
            "GET", "http://test/api/x", return_headers=True
        )
        assert "raw_content" in data
        assert "content-type" in headers

    @pytest.mark.asyncio
    async def test_connect_error(self):
        """ConnectError raises GrampsAPIError."""
        client = self._setup_client()
        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(GrampsAPIError, match="Cannot connect"):
            await client._make_request("GET", "http://test/api/people/")

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """TimeoutException raises GrampsAPIError."""
        client = self._setup_client()
        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )

        with pytest.raises(GrampsAPIError, match="timeout"):
            await client._make_request("GET", "http://test/api/people/")

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        """Non-httpx exceptions are caught and wrapped in GrampsAPIError."""
        client = self._setup_client()
        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(
            side_effect=RuntimeError("something unexpected")
        )

        with pytest.raises(GrampsAPIError, match="Unexpected error"):
            await client._make_request("GET", "http://test/api/people/")

    @pytest.mark.asyncio
    async def test_json_with_return_headers(self):
        """Valid JSON + return_headers returns (data, headers)."""
        client = self._setup_client()

        resp = MagicMock()
        resp.status_code = 200
        resp.text = '{"id": 1}'
        resp.headers = {"x-total-count": "42"}
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"id": 1}

        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock(return_value=resp)

        data, headers = await client._make_request(
            "GET", "http://test/api/people/", return_headers=True
        )
        assert data == {"id": 1}
        assert headers["x-total-count"] == "42"


# ---------------------------------------------------------------------------
# make_api_call
# ---------------------------------------------------------------------------


class TestMakeApiCall:
    """Test make_api_call routing, parameter handling, and list_mode."""

    def _make_client(self) -> GrampsWebAPIClient:
        client = GrampsWebAPIClient()
        client.auth_manager = MagicMock()
        client.auth_manager.get_token = AsyncMock()
        client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        client.auth_manager.client = MagicMock()
        client.auth_manager.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_tree_id_substitution(self):
        """Endpoint with {tree_id} gets tree_id substituted."""
        client = self._make_client()

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"name": "My Tree"}

            await client.make_api_call(
                api_call=ApiCalls.GET_TREE,
                params=None,
                tree_id="my_tree_123",
            )

            call_url = mock_req.call_args.kwargs["url"]
            assert "my_tree_123" in call_url

    @pytest.mark.asyncio
    async def test_get_uses_query_params(self):
        """GET requests pass validated params as query parameters."""
        client = self._make_client()

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []

            await client.make_api_call(
                api_call=ApiCalls.GET_PEOPLE,
                params={"pagesize": 10, "page": 1},
            )

            call_kwargs = mock_req.call_args.kwargs
            assert call_kwargs["params"]["pagesize"] == 10
            assert call_kwargs["json_data"] is None

    @pytest.mark.asyncio
    async def test_post_uses_json_body(self):
        """POST requests use JSON body, not query params."""
        client = self._make_client()

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"handle": "new123"}

            await client.make_api_call(
                api_call=ApiCalls.POST_EVENTS,
                params={"type": "Birth", "citation_list": []},
            )

            call_kwargs = mock_req.call_args.kwargs
            assert call_kwargs["json_data"] is not None
            assert call_kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_post_report_file_uses_query_params(self):
        """POST_REPORT_FILE is a special case that uses query params."""
        client = self._make_client()

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"task": {"id": "t1"}}

            await client.make_api_call(
                api_call=ApiCalls.POST_REPORT_FILE,
                params={"options": '{"pid": "I0001"}'},
                report_id="descend_report",
            )

            call_kwargs = mock_req.call_args.kwargs
            assert call_kwargs["params"] is not None
            assert call_kwargs["json_data"] is None

    @pytest.mark.asyncio
    async def test_put_replace_mode(self):
        """list_mode='replace' replaces _list fields instead of merging."""
        client = self._make_client()

        name_data = {
            "first_name": "John",
            "surname_list": [{"surname": "Smith"}],
        }
        existing = {
            "handle": "p1",
            "gramps_id": "I001",
            "primary_name": name_data,
            "gender": 1,
            "event_ref_list": [{"ref": "old_event", "role": "Primary"}],
        }

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [existing, {"success": True}]

            await client.make_api_call(
                api_call=ApiCalls.PUT_PERSON,
                params={
                    "handle": "p1",
                    "primary_name": name_data,
                    "gender": 1,
                    "event_ref_list": [{"ref": "new_event", "role": "Primary"}],
                    "list_mode": "replace",
                },
                handle="p1",
            )

            put_call = mock_req.call_args_list[1]
            put_data = put_call.kwargs["json_data"]
            # Replace mode: only the new event, not merged
            assert len(put_data["event_ref_list"]) == 1
            assert put_data["event_ref_list"][0]["ref"] == "new_event"

    @pytest.mark.asyncio
    async def test_with_headers_forwarded(self):
        """with_headers=True is forwarded to _make_request."""
        client = self._make_client()

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = ([], {"x-total-count": "0"})

            await client.make_api_call(
                api_call=ApiCalls.GET_SEARCH,
                params={"query": "test"},
                with_headers=True,
            )

            call_kwargs = mock_req.call_args.kwargs
            assert call_kwargs["return_headers"] is True


# ---------------------------------------------------------------------------
# upload_media_file
# ---------------------------------------------------------------------------


class TestMediaClientUpload:
    """Test MediaClient.upload_media_file."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        api_client = GrampsWebAPIClient()
        api_client.auth_manager = MagicMock()
        api_client.auth_manager.get_token = AsyncMock()
        api_client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        api_client.auth_manager.close = AsyncMock()

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = [{"new": {"handle": "m1"}}]

        api_client.auth_manager.client = MagicMock()
        api_client.auth_manager.client.request = AsyncMock(return_value=resp)

        media_client = MediaClient(api_client)
        result = await media_client.upload_media_file(b"content", "image/jpeg")
        assert result == [{"new": {"handle": "m1"}}]

        # Verify Content-Type header was set
        call_kwargs = api_client.auth_manager.client.request.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_413_payload_too_large(self):
        """413 from server propagates as HTTPStatusError."""
        api_client = GrampsWebAPIClient()
        api_client.auth_manager = MagicMock()
        api_client.auth_manager.get_token = AsyncMock()
        api_client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        api_client.auth_manager.close = AsyncMock()

        request = httpx.Request("POST", "http://test/api/media/")
        response = httpx.Response(413, request=request)
        error = httpx.HTTPStatusError("413", request=request, response=response)

        resp = MagicMock()
        resp.raise_for_status = MagicMock(side_effect=error)

        api_client.auth_manager.client = MagicMock()
        api_client.auth_manager.client.request = AsyncMock(return_value=resp)

        media_client = MediaClient(api_client)
        with pytest.raises(httpx.HTTPStatusError):
            await media_client.upload_media_file(b"huge" * 1000, "image/png")

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """ConnectError during upload propagates."""
        api_client = GrampsWebAPIClient()
        api_client.auth_manager = MagicMock()
        api_client.auth_manager.get_token = AsyncMock()
        api_client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        api_client.auth_manager.close = AsyncMock()

        api_client.auth_manager.client = MagicMock()
        api_client.auth_manager.client.request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        media_client = MediaClient(api_client)
        with pytest.raises(httpx.ConnectError):
            await media_client.upload_media_file(b"content", "image/jpeg")


# ---------------------------------------------------------------------------
# bulk_delete
# ---------------------------------------------------------------------------


class TestBulkDelete:
    """Test bulk_delete() input validation and request building."""

    def _make_client(self):
        """Build a GrampsWebAPIClient with mocked internals."""
        client = GrampsWebAPIClient()
        client.auth_manager = MagicMock()
        client.auth_manager.get_token = AsyncMock()
        client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        client.auth_manager.client = MagicMock()
        client.auth_manager.client.request = AsyncMock()
        client.auth_manager.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_rejects_empty_list(self):
        """Empty items list raises ValueError."""
        client = self._make_client()
        with pytest.raises(ValueError, match="non-empty"):
            await client.bulk_delete(items=[])

    @pytest.mark.asyncio
    async def test_rejects_malformed_items(self):
        """Items missing _class or handle raise ValueError."""
        client = self._make_client()
        with pytest.raises(ValueError, match="_class"):
            await client.bulk_delete(items=[{"handle": "h1"}])

    @pytest.mark.asyncio
    async def test_rejects_non_dict_items(self):
        """Non-dict items raise ValueError."""
        client = self._make_client()
        with pytest.raises(ValueError, match="_class"):
            await client.bulk_delete(items=["not a dict"])

    @pytest.mark.asyncio
    async def test_builds_correct_request(self):
        """Successful call posts to objects/delete/ with correct payload."""
        client = self._make_client()
        client._make_request = AsyncMock(return_value={})

        await client.bulk_delete(
            items=[{"_class": "Tag", "handle": "t1"}], tree_id="mytree"
        )

        client._make_request.assert_called_once()
        call_kwargs = client._make_request.call_args
        method = call_kwargs.kwargs.get("method") or call_kwargs.args[0]
        assert method == "POST"
        url = call_kwargs.kwargs.get("url") or call_kwargs.args[1]
        assert "objects/delete/" in url
        json_data = call_kwargs.kwargs.get("json_data")
        assert json_data == [{"_class": "Tag", "handle": "t1"}]


# ---------------------------------------------------------------------------
# replace_media_file
# ---------------------------------------------------------------------------


class TestMediaClientReplace:
    """Test MediaClient.replace_media_file() request building and error handling."""

    def _make_api_client(self):
        """Build a GrampsWebAPIClient with mocked internals."""
        api_client = GrampsWebAPIClient()
        api_client.auth_manager = MagicMock()
        api_client.auth_manager.get_token = AsyncMock()
        api_client.auth_manager.get_headers = MagicMock(
            return_value={"Authorization": "Bearer test"}
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "{}"
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        api_client.auth_manager.client = MagicMock()
        api_client.auth_manager.client.request = AsyncMock(return_value=mock_response)
        api_client.auth_manager.close = AsyncMock()
        return api_client

    @pytest.mark.asyncio
    async def test_builds_correct_put_request(self):
        """Sends PUT to media/{handle}/file with correct content-type."""
        api_client = self._make_api_client()
        media_client = MediaClient(api_client)

        await media_client.replace_media_file(
            file_content=b"image data",
            handle="m1",
            mime_type="image/jpeg",
            tree_id="tree1",
        )

        call = api_client.auth_manager.client.request
        call.assert_awaited_once()
        call_kwargs = call.call_args[1]
        assert call_kwargs["method"] == "PUT"
        assert "media/m1/file" in call_kwargs["url"]
        assert call_kwargs["content"] == b"image data"
        assert call_kwargs["headers"]["Content-Type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_empty_response_returns_dict(self):
        """Empty response body returns empty dict."""
        api_client = self._make_api_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "   "
        mock_response.raise_for_status = MagicMock()
        api_client.auth_manager.client.request = AsyncMock(return_value=mock_response)

        media_client = MediaClient(api_client)
        result = await media_client.replace_media_file(
            file_content=b"data",
            handle="m1",
            mime_type="image/png",
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_http_error_raises_gramps_error(self):
        """HTTP errors are converted to GrampsAPIError."""
        api_client = self._make_api_client()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_request = MagicMock()
        mock_request.url = "http://localhost/api/media/bad/file"
        mock_response.request = mock_request
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=mock_request, response=mock_response
        )
        api_client.auth_manager.client.request = AsyncMock(return_value=mock_response)

        media_client = MediaClient(api_client)
        with pytest.raises(GrampsAPIError):
            await media_client.replace_media_file(
                file_content=b"data",
                handle="bad",
                mime_type="image/jpeg",
            )
