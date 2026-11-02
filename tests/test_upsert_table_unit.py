# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the generic table-driven upsert (#102). No Docker.

A fake client records the call order so the fixed sequence (parse,
reference checks, write, media upload) and "no write before every check
passes" are checked without a server.
"""

from dataclasses import replace

import pytest

from src.gramps_mcp.models.parameters.event_params import EventSaveParams
from src.gramps_mcp.overlays import WRITE_BINDINGS
from src.gramps_mcp.tools import upsert_table
from src.gramps_mcp.tools._data_helpers import _CITATION_NUDGE
from src.gramps_mcp.tools._errors import McpToolError
from src.gramps_mcp.tools.upsert_table import UPSERT_HANDLERS, upsert_entity

_SAVED = {"handle": "h1", "gramps_id": "E1"}


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
        """Record the close."""
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
        "GrampsWebAPIClient",
        lambda: _FakeClient(calls, calls.fail_with),
    )

    async def _fmt(client, data, entity, operation, tree_id, nudge):
        calls.append(("format", entity, operation, nudge))
        return f"{operation} {entity} nudge={nudge}"

    monkeypatch.setattr(upsert_table, "_format_save_response", _fmt)
    return calls


def _hook(log, name, fail=False):
    """
    Build an async hook that logs its name and optionally raises.

    Args:
        log (list): Shared call log.
        name (str): Name logged when the hook runs.
        fail (bool): Raise McpToolError after logging.

    Returns:
        Callable: The hook.
    """

    async def hook(client, tree_id, params):
        """Log, then raise when asked."""
        log.append(("hook", name))
        if fail:
            raise McpToolError(f"{name} failed")

    return hook


class TestOrdering:
    """Parse, reference checks, write, then media upload."""

    async def test_checks_then_write_then_upload(self, log):
        """Hooks run around the write in the fixed order."""
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
            ("call", "PUT", "events/{handle}", {"handle": "h1"}),
            ("hook", "upload"),
            ("format", "event", "updated", False),
            ("close",),
        ]

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
        assert log == [("hook", "check"), ("close",)]

    async def test_parse_failure_makes_no_call(self, log):
        """Invalid arguments fail before a client exists."""
        with pytest.raises(McpToolError) as info:
            await upsert_entity("event", {"handle": "h1", "bogus": 1})
        assert (log, "bogus" in str(info.value)) == ([], True)

    async def test_four_entities_bind_no_hooks(self, log):
        """Event, place, source and note bind no checks and no upload."""
        assert {
            e: (b.reference_checks, b.media_upload) for e, b in WRITE_BINDINGS.items()
        } == {e: ((), None) for e in ("event", "place", "source", "note")}


class TestRouting:
    """handle picks PUT on the item path, otherwise POST on the collection."""

    @pytest.mark.parametrize(
        ("entity", "arguments", "expected"),
        [
            ("event", {"type": "Birth"}, ("POST", "events/", {})),
            ("place", {"handle": "p1"}, ("PUT", "places/{handle}", {"handle": "p1"})),
            ("source", {"title": "T"}, ("POST", "sources/", {})),
            (
                "note",
                {"text": "x", "type": "General"},
                ("POST", "notes/", {}),
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
            ("event", {"type": "Birth"}, True),
            ("event", {"type": "Birth", "citation_list": ["c1"]}, False),
            ("event", {"handle": "h1"}, False),
            ("place", {"place_type": "City"}, True),
            ("source", {"title": "T"}, False),
            ("note", {"text": "x", "type": "General"}, False),
        ],
    )
    async def test_nudge(self, log, entity, arguments, expected):
        """Event and place nudge on create without citations."""
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
            e: f"upsert_{e}_tool" for e in ("event", "place", "source", "note")
        }
