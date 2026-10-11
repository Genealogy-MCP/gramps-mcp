# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for GrampsWebAPIClient.call_resource and api_body (#102).

Table rows call the client by (method, path template, params model). The
entry point shares the PUT merge and list_mode path with make_api_call,
so these tests pin both sides to the same request. No network.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.gramps_mcp.client import GrampsWebAPIClient, api_body
from src.gramps_mcp.models.api_calls import ApiCalls
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.models.parameters.note_params import NoteSaveParams
from src.gramps_mcp.models.parameters.tag_params import TagSaveParams


def _client():
    """Build a client whose base URL is fixed for URL assertions."""
    client = GrampsWebAPIClient()
    client.base_url = "http://gramps.test/api"
    return client


class TestApiBody:
    """api_body builds the JSON body and pulls list_mode out of it."""

    def test_uses_payload_hook(self):
        """NoteSaveParams wraps text into StyledText through its hook."""
        body, mode = api_body(NoteSaveParams(text="hi", type="General"))
        assert (body["text"], mode) == (
            {"_class": "StyledText", "string": "hi"},
            "merge",
        )

    def test_plain_model_dumped(self):
        """A model without the hook is dumped with None values dropped."""
        assert api_body(TagSaveParams(name="x")) == ({"name": "x"}, "merge")

    def test_url_description_normalised(self):
        """A urls entry's description becomes desc."""
        from pydantic import BaseModel

        class _Linked(BaseModel):
            urls: list
            list_mode: str

        params = _Linked(urls=[{"path": "p", "description": "d"}], list_mode="replace")
        body, mode = api_body(params)
        assert (body, mode) == ({"urls": [{"path": "p", "desc": "d"}]}, "replace")


class TestCallResource:
    """call_resource sends the same request make_api_call sends."""

    @pytest.mark.asyncio
    async def test_post_on_collection_path(self):
        """POST goes to the collection path with the hook's body."""
        client = _client()
        with patch.object(client, "_make_request", new_callable=AsyncMock) as req:
            req.return_value = [{"new": {"handle": "n1"}}]
            await client.call_resource(
                "POST", "notes/", NoteSaveParams(text="hi", type="General")
            )
        assert req.await_args_list[0].kwargs == {
            "method": "POST",
            "url": "http://gramps.test/api/notes/",
            "params": None,
            "json_data": {
                "text": {"_class": "StyledText", "string": "hi"},
                "type": "General",
            },
            "return_headers": False,
            "raw": False,
        }

    @pytest.mark.asyncio
    async def test_put_merges_with_stored_record(self):
        """PUT GETs the item, merges per list_mode, then PUTs the result."""
        client = _client()
        stored = {"handle": "e1", "note_list": ["n0"], "description": "old"}
        with patch.object(client, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [stored, {}]
            await client.call_resource(
                "PUT",
                "events/{handle}",
                EventSaveParams(handle="e1", note_list=["n1"]),
                handle="e1",
            )
        get_call, put_call = req.await_args_list
        assert (get_call.args, put_call.kwargs["json_data"]) == (
            ("GET", "http://gramps.test/api/events/e1"),
            {"handle": "e1", "note_list": ["n0", "n1"], "description": "old"},
        )

    @pytest.mark.asyncio
    async def test_matches_make_api_call(self):
        """The table entry point and the enum entry point send one request."""
        sent = []
        for use_table in (True, False):
            client = _client()
            params = EventSaveParams(handle="e1", note_list=["n1"], list_mode="replace")
            with patch.object(client, "_make_request", new_callable=AsyncMock) as req:
                req.side_effect = [{"handle": "e1", "note_list": ["n0"]}, {}]
                if use_table:
                    await client.call_resource(
                        "PUT", "events/{handle}", params, handle="e1"
                    )
                else:
                    await client.make_api_call(
                        ApiCalls.PUT_EVENT, params=params, handle="e1"
                    )
            sent.append([(c.args, c.kwargs) for c in req.await_args_list])
        assert sent[0] == sent[1]

    @pytest.mark.asyncio
    async def test_handle_is_percent_encoded(self):
        """A crafted handle cannot escape its path segment (MCP-18)."""
        client = _client()
        with patch.object(client, "_make_request", new_callable=AsyncMock) as req:
            req.side_effect = [{}, {}]
            await client.call_resource(
                "PUT", "events/{handle}", EventSaveParams(handle="a/b"), handle="a/b"
            )
        assert req.await_args_list[-1].kwargs["url"] == (
            "http://gramps.test/api/events/a%2Fb"
        )

    @pytest.mark.asyncio
    async def test_unknown_method_rejected(self):
        """Only the write verbs a table row can carry are accepted."""
        with pytest.raises(ValueError, match="PATCH"):
            await _client().call_resource(
                "PATCH", "events/", EventSaveParams(handle="h")
            )
