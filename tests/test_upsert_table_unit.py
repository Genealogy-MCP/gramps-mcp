# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the generic table-driven upsert (#102, #103). No Docker.

A fake client records the call order so the fixed sequence (parse,
reference checks, media upload, write) and "no write before every check
passes" are checked without a server.
"""

import re
from dataclasses import replace
from unittest.mock import ANY

import pytest

from src.gramps_mcp.auth import GrampsAuthError
from src.gramps_mcp.client import GrampsAPIError
from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.tools import upsert_table
from src.gramps_mcp.tools._data_helpers import _CITATION_NUDGE
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS, upsert_entity
from src.gramps_mcp.write_hooks import (
    check_citation_source,
    check_person_refs,
    format_tag_save,
    has_event_refs,
    upload_media,
)
from src.gramps_mcp.write_overlays import WRITE_BINDINGS

_ENTITIES = (
    "person",
    "family",
    "event",
    "place",
    "source",
    "citation",
    "note",
    "media",
    "repository",
    "tag",
)

_SAVED = {"handle": "h1", "gramps_id": "E1"}
_NAME = {"first_name": "A", "surname_list": []}


class _FakeClient:
    """Client double that logs every call and returns a saved record."""

    def __init__(self, log, fail_with=None):
        """
        Store the shared call log.

        Args:
            log (list): Shared list the fake appends call records to.
            fail_with (Exception | None): Raised by call_resource when set.
        """
        self.log = log
        self.fail_with = fail_with

    async def call_resource(self, method, path, params=None, tree_id=None, **kw):
        """
        Record a resource call.

        Args:
            method (str): HTTP verb.
            path (str): Path template.
            params: Parsed model.
            tree_id (str): Tree id.
            **kw: Path placeholders.

        Returns:
            dict: The saved record.
        """
        self.log.append(("call", method, path, kw))
        if self.fail_with:
            raise self.fail_with
        return _SAVED

    async def close(self):
        """Record a close; the shared client must never log one."""
        self.log.append(("close",))


class _Log(list):
    """Call log that also carries the error the fake client should raise."""

    fail_with = None


@pytest.fixture
def log(monkeypatch):
    """Patch client, settings and formatter; return the shared call log."""
    calls = _Log()

    class _Settings:
        gramps_tree_id = "tree"

    monkeypatch.setattr(upsert_table, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        upsert_table,
        "get_client",
        lambda: _FakeClient(calls, calls.fail_with),
    )

    async def _fmt(client, data, entity, operation, tree_id, nudge):
        calls.append(("format", entity, operation, nudge))
        return f"{operation} {entity} nudge={nudge}"

    monkeypatch.setattr(upsert_table, "_format_save_response", _fmt)
    return calls


def _hook(log, name, fail=False, returns=None):
    """
    Build an async hook that logs its name and optionally raises.

    Args:
        log (list): Shared call log.
        name (str): Name logged when the hook runs.
        fail (bool): Raise McpToolError after logging.
        returns: Value the hook returns (an upload's new handle).

    Returns:
        Callable: The hook.
    """

    async def hook(client, tree_id, params):
        """Log, then raise when asked."""
        log.append(("hook", name))
        if fail:
            raise McpToolError(f"{name} failed")
        return returns

    return hook


class TestOrdering:
    """Parse, reference checks, media upload, then the write."""

    async def test_checks_then_upload_then_write(self, log):
        """Hooks run before the write in the fixed order."""
        bindings = {
            "event": replace(
                WRITE_BINDINGS["event"],
                reference_checks=(_hook(log, "check1"), _hook(log, "check2")),
                media_upload=_hook(log, "upload"),
            )
        }
        await upsert_entity("event", {"handle": "h1"}, bindings=bindings)
        assert log == [
            ("hook", "check1"),
            ("hook", "check2"),
            ("hook", "upload"),
            ("call", "PUT", "events/{handle}", {"handle": "h1"}),
            ("format", "event", "updated", False),
        ]

    async def test_upload_handle_turns_create_into_put(self, log):
        """A handle returned by the upload is PUT on and reported as created."""
        bindings = {
            "event": replace(
                WRITE_BINDINGS["event"],
                media_upload=_hook(log, "upload", returns="new1"),
            )
        }
        await upsert_entity("event", {"type": "Birth"}, bindings=bindings)
        assert log == [
            ("hook", "upload"),
            ("call", "PUT", "events/{handle}", {"handle": "new1"}),
            ("format", "event", "created", True),
        ]

    async def test_failed_put_after_upload_names_the_record(self, log):
        """A PUT failing after the upload says to retry on the stored handle."""
        log.fail_with = GrampsAPIError("Server error (500).", status_code=500)
        bindings = {
            "event": replace(
                WRITE_BINDINGS["event"],
                media_upload=_hook(log, "upload", returns="new1"),
            )
        }
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"type": "Birth"}, bindings=bindings)
        assert str(info.value) == (
            "Server error (500). The event file is stored as handle `new1`, but "
            "its fields may not be saved. Retry with handle `new1` to update "
            "that record, so a retry makes no duplicate."
        )

    async def test_failed_update_put_raises_as_is(self, log):
        """A PUT failing on an update keeps the plain error."""
        log.fail_with = GrampsAPIError("Server error (500).", status_code=500)
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"handle": "h1", "type": "Birth"})
        assert str(info.value) == "Server error (500)."

    async def test_failed_check_blocks_write(self, log):
        """No write or upload happens when a reference check fails."""
        bindings = {
            "event": replace(
                WRITE_BINDINGS["event"],
                reference_checks=(_hook(log, "check", fail=True),),
                media_upload=_hook(log, "upload"),
            )
        }
        with pytest.raises(McpToolError, match="^check failed$"):
            await upsert_entity("event", {"handle": "h1"}, bindings=bindings)
        assert log == [("hook", "check")]

    async def test_parse_failure_makes_no_call(self, log):
        """Invalid arguments fail before a client exists."""
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"handle": "h1", "bogus": 1})
        assert (log, "bogus" in str(info.value)) == ([], True)

    async def test_bound_hooks(self, log):
        """Person checks refs and re-saves, citation checks, media uploads."""
        no_hooks = ((), None, None, None, None)
        assert {
            e: (
                b.reference_checks,
                b.media_upload,
                b.empty_arguments_error,
                b.format_response,
                b.resave_after_create,
            )
            for e, b in WRITE_BINDINGS.items()
        } == {
            **{e: no_hooks for e in _ENTITIES},
            "person": ((check_person_refs,), None, None, None, has_event_refs),
            "citation": ((check_citation_source,), None, None, None, None),
            "media": (
                (),
                upload_media,
                "file_location is required to create new media.",
                None,
                None,
            ),
            "tag": ((), None, None, format_tag_save, None),
        }

    async def test_empty_arguments_error(self, log):
        """Media with no arguments fails with its message and no call."""
        with pytest.raises(McpToolError) as info:
            await upsert_entity("media", {})
        assert (log, str(info.value)) == (
            [],
            "Unexpected error during media save: "
            "file_location is required to create new media.",
        )

    async def test_format_response_replaces_formatter(self, log):
        """A bound response formatter builds the confirmation."""
        result = await upsert_entity("tag", {"name": "T"})
        assert ([e[0] for e in log], result[0].text.splitlines()[0]) == (
            ["call"],
            "Successfully created tag:",
        )


class TestRouting:
    """handle picks PUT on the item path, otherwise POST on the collection."""

    @pytest.mark.parametrize(
        ("entity", "arguments", "expected"),
        [
            ("event", {"type": "Birth"}, ("POST", "events/", {"handle": ANY})),
            ("place", {"handle": "p1"}, ("PUT", "places/{handle}", {"handle": "p1"})),
            ("source", {"title": "T"}, ("POST", "sources/", {"handle": ANY})),
            (
                "note",
                {"text": "x", "type": "General"},
                ("POST", "notes/", {"handle": ANY}),
            ),
        ],
    )
    async def test_path_from_row(self, log, entity, arguments, expected):
        """The verb and path come from the table row."""
        await upsert_entity(entity, arguments)
        assert log[0] == ("call", *expected)

    async def test_accepts_parsed_model(self, log):
        """A pre-validated model is used as is."""
        await upsert_entity("event", EventSaveParams(handle="h9"))
        assert log[0] == ("call", "PUT", "events/{handle}", {"handle": "h9"})


class TestNudge:
    """The citation nudge follows the binding, only on create."""

    @pytest.mark.parametrize(
        ("entity", "arguments", "expected"),
        [
            ("person", {"gender": 1, "primary_name": _NAME}, True),
            (
                "person",
                {"gender": 1, "primary_name": _NAME, "citation_list": ["c1"]},
                False,
            ),
            ("event", {"type": "Birth"}, True),
            ("event", {"type": "Birth", "citation_list": ["c1"]}, False),
            ("event", {"handle": "h1"}, False),
            ("place", {"place_type": "City"}, True),
            ("source", {"title": "T"}, False),
            ("note", {"text": "x", "type": "General"}, False),
            ("family", {"father_handle": "p1"}, False),
            ("repository", {"name": "R", "type": "Library"}, False),
        ],
    )
    async def test_nudge(self, log, entity, arguments, expected):
        """Person, event and place nudge on create without citations."""
        await upsert_entity(entity, arguments)
        assert log[1][3] is expected

    def test_nudge_text_unchanged(self):
        """The nudge wording is the pre-#102 text."""
        assert _CITATION_NUDGE == (
            "> Note: created without a citation. "
            "Consider adding a source to support this record."
        )


class TestErrors:
    """Error context is per entity; McpToolError passes through bare."""

    async def test_unexpected_error_gets_entity_context(self, log):
        """A non-tool error is wrapped with '<entity> save'."""
        log.fail_with = RuntimeError("boom")
        with pytest.raises(McpToolError) as info:
            await upsert_entity("source", {"title": "T"})
        assert str(info.value) == "Unexpected error during source save: boom"

    async def test_tool_error_reraised_bare(self, log):
        """An McpToolError keeps its object and message."""
        error = McpToolError("exact text")
        log.fail_with = error
        with pytest.raises(McpToolError) as info:
            await upsert_entity("note", {"text": "x", "type": "General"})
        assert info.value is error


class TestHandlers:
    """make_upsert_handler adapts the (ctx, params) convention."""

    async def test_handler_dict_and_model(self, log):
        """Legacy dict and library (ctx, model) calls both reach the API."""
        handler = UPSERT_HANDLERS["event"]
        await handler({"handle": "a"})
        await handler(None, EventSaveParams(handle="b"))
        assert [entry[3] for entry in log if entry[0] == "call"] == [
            {"handle": "a"},
            {"handle": "b"},
        ]

    def test_handler_names(self):
        """Handlers keep the historical tool names."""
        assert {e: h.__name__ for e, h in UPSERT_HANDLERS.items()} == {
            e: f"upsert_{e}_tool" for e in _ENTITIES
        }


class _ScriptedClient:
    """Client double answering POST and GET from a script (#106)."""

    def __init__(self, post, get=None):
        """
        Store the scripted outcomes.

        Args:
            post (Exception | dict): Raised or returned by the POST.
            get (Exception | dict | None): Raised or returned by the GET.
        """
        self.script = {"POST": post, "GET": get}
        self.calls = []
        self.models = []

    async def call_resource(self, method, path, params=None, tree_id=None, **kw):
        """
        Record the call and play its scripted outcome.

        Args:
            method (str): HTTP verb.
            path (str): Path template.
            params: Parsed model.
            tree_id (str): Tree id.
            **kw: Path placeholders.

        Returns:
            dict: The scripted record.
        """
        self.calls.append((method, path, kw["handle"]))
        self.models.append(params)
        outcome = self.script[method]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


_POST_500 = GrampsAPIError("Server error (500) at /records/.", status_code=500)
_POST_TIMEOUT = GrampsAPIError("Request timeout: read.", request_sent=True)


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted client; return a setter for its script."""

    class _Settings:
        gramps_tree_id = "tree"

    monkeypatch.setattr(upsert_table, "get_settings", lambda: _Settings())

    async def _fmt(client, data, entity, operation, tree_id, nudge):
        return f"{operation} {data['gramps_id']}"

    monkeypatch.setattr(upsert_table, "_format_save_response", _fmt)

    def install(post, get=None):
        client = _ScriptedClient(post, get)
        monkeypatch.setattr(upsert_table, "get_client", lambda: client)
        return client

    return install


class TestCreateServerError:
    """A 5xx on create is checked against the stored record (#106)."""

    async def test_create_sends_fresh_handle(self, scripted):
        """Each create POSTs a new 32-hex handle chosen client side."""
        client = scripted(_SAVED)
        await upsert_entity("event", {"type": "Birth"})
        await upsert_entity("event", {"type": "Birth"})
        first, second = (handle for _, _, handle in client.calls)
        assert (re.fullmatch(r"[0-9a-f]{32}", first) is not None, first != second) == (
            True,
            True,
        )

    async def test_landed_write_reports_created(self, scripted):
        """A 5xx whose record exists is reported as a normal create."""
        client = scripted(_POST_500, {"handle": "x", "gramps_id": "I9"})
        result = await upsert_entity("person", {"gender": 1, "primary_name": _NAME})
        handle = client.calls[0][2]
        assert (result[0].text, client.calls) == (
            "created I9",
            [("POST", "people/", handle), ("GET", "people/{handle}", handle)],
        )

    async def test_missing_record_says_retry_is_safe(self, scripted):
        """A 5xx with no stored record says nothing was written."""
        client = scripted(
            _POST_500, GrampsAPIError("Record not found.", status_code=404)
        )
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"type": "Birth"})
        assert str(info.value) == (
            "Server error (500) at /records/. Nothing was written: no event "
            f"has handle `{client.calls[0][2]}`, so a retry makes no duplicate."
        )

    async def test_failed_check_names_the_handle(self, scripted):
        """When the check fails too, the error names the handle to look up."""
        client = scripted(
            _POST_500, GrampsAPIError("Server error (502).", status_code=502)
        )
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"type": "Birth"})
        assert str(info.value) == (
            "Server error (500) at /records/. The event may have been written. "
            f"Get handle `{client.calls[0][2]}` before retrying, "
            "so a retry makes no duplicate."
        )

    async def test_create_model_stays_handle_free(self, scripted):
        """The handle travels beside the model, so it still serialises as a create."""
        client = scripted(_SAVED)
        await upsert_entity("family", {"child_ref_list": [{"ref": "c1"}]})
        assert client.models[0].to_api_payload()["child_ref_list"] == [
            {"ref": "c1", "frel": "Birth", "mrel": "Birth"}
        ]

    async def test_auth_failure_on_check_names_the_handle(self, scripted):
        """A login failure during the check still names the handle to look up."""
        client = scripted(_POST_500, GrampsAuthError("Login failed.", status_code=500))
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"type": "Birth"})
        assert f"Get handle `{client.calls[0][2]}` before retrying" in str(info.value)

    async def test_client_error_is_not_checked(self, scripted):
        """A 4xx on create raises as is, with no GET."""
        client = scripted(GrampsAPIError("Bad request.", status_code=400))
        with pytest.raises(McpToolError, match=r"^Bad request\.$"):
            await upsert_entity("event", {"type": "Birth"})
        assert [method for method, _, _ in client.calls] == ["POST"]

    async def test_update_error_is_not_checked(self, scripted):
        """A 5xx on update raises as is: a PUT retry makes no duplicate."""
        client = scripted(None)
        client.script["PUT"] = _POST_500
        with pytest.raises(McpToolError, match=r"^Server error \(500\)"):
            await upsert_entity("event", {"handle": "h1"})
        assert client.calls == [("PUT", "events/{handle}", "h1")]


_EVENT_REFS = [{"ref": "e1", "role": "Primary"}]


class TestResaveAfterCreate:
    """A person create with events is PUT back so Gramps sets its indexes (#134)."""

    async def test_person_with_events_is_put_back(self, scripted):
        """The POST is followed by a replace-mode PUT on the new handle."""
        client = scripted(_SAVED)
        client.script["PUT"] = {"handle": "h1", "gramps_id": "I1"}
        result = await upsert_entity(
            "person",
            {"gender": 1, "primary_name": _NAME, "event_ref_list": _EVENT_REFS},
        )
        resave = client.models[1].to_api_payload()
        assert (
            result[0].text,
            client.calls,
            resave["list_mode"],
            resave["event_ref_list"],
        ) == (
            "created I1",
            [("POST", "people/", client.calls[0][2]), ("PUT", "people/{handle}", "h1")],
            "replace",
            client.models[0].to_api_payload()["event_ref_list"],
        )

    @pytest.mark.parametrize(
        ("entity", "arguments"),
        [
            ("person", {"gender": 1, "primary_name": _NAME}),
            ("event", {"type": "Birth"}),
        ],
    )
    async def test_no_resave_without_event_refs(self, scripted, entity, arguments):
        """A person without events, or another entity, is POSTed only."""
        client = scripted(_SAVED)
        await upsert_entity(entity, arguments)
        assert [method for method, _, _ in client.calls] == ["POST"]

    async def test_update_is_not_resaved(self, scripted):
        """An update already runs the server's index step: one PUT."""
        client = scripted(None)
        client.script["PUT"] = _SAVED
        await upsert_entity("person", {"handle": "h1", "event_ref_list": _EVENT_REFS})
        assert client.calls == [("PUT", "people/{handle}", "h1")]

    async def test_failed_resave_names_the_record(self, scripted):
        """A failed re-save says the person is stored and how to retry."""
        client = scripted(_SAVED)
        client.script["PUT"] = GrampsAPIError("Server error (500).", status_code=500)
        with pytest.raises(McpToolError) as info:
            await upsert_entity(
                "person",
                {"gender": 1, "primary_name": _NAME, "event_ref_list": _EVENT_REFS},
            )
        assert str(info.value) == (
            "Server error (500). The person is stored as handle `h1`, but its "
            "birth and death indexes may not be saved. Retry with handle `h1` "
            "to update that record, so a retry makes no duplicate."
        )


class TestCreateTimeout:
    """A create that times out is checked like a 5xx; a connect error is not (#130)."""

    async def test_landed_write_reports_created(self, scripted):
        """A timed-out create whose record exists is reported as a normal create."""
        client = scripted(_POST_TIMEOUT, {"handle": "x", "gramps_id": "E9"})
        result = await upsert_entity("event", {"type": "Birth"})
        handle = client.calls[0][2]
        assert (result[0].text, client.calls) == (
            "created E9",
            [("POST", "events/", handle), ("GET", "events/{handle}", handle)],
        )

    async def test_missing_record_says_the_save_may_still_land(self, scripted):
        """A 404 after a timeout does not claim nothing was written."""
        client = scripted(
            _POST_TIMEOUT, GrampsAPIError("Record not found.", status_code=404)
        )
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"type": "Birth"})
        handle = client.calls[0][2]
        assert str(info.value) == (
            f"Request timeout: read. No event has handle `{handle}` yet, but "
            "the server may still be saving it. Get handle "
            f"`{handle}` before retrying, so a retry makes no duplicate."
        )

    async def test_connect_error_is_not_checked(self, scripted):
        """A request that never left raises as is, with no GET."""
        client = scripted(GrampsAPIError("Cannot connect to Gramps API: refused"))
        with pytest.raises(McpToolError, match="^Cannot connect"):
            await upsert_entity("event", {"type": "Birth"})
        assert [method for method, _, _ in client.calls] == ["POST"]
