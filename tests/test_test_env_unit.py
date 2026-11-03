# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for the test-instance environment resolution."""

import pytest

from tests import _test_env
from tests._test_env import (
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    UNREACHABLE_API_URL,
    parse_published_url,
    resolve_base_url,
    resolve_test_env,
)

LOCAL_URL = "http://127.0.0.1:54321"

_LOCAL_DEFAULTS = {
    "GRAMPS_API_URL": LOCAL_URL,
    "GRAMPS_USERNAME": DEFAULT_USERNAME,
    "GRAMPS_PASSWORD": DEFAULT_PASSWORD,
}


def _local_stack() -> str:
    return LOCAL_URL


def _no_stack() -> None:
    return None


def _must_not_discover() -> None:
    pytest.fail("an explicit GRAMPS_API_URL must not trigger stack discovery")


def test_empty_environment_targets_own_stack():
    assert resolve_test_env({}, _local_stack) == (_LOCAL_DEFAULTS, [])


def test_empty_environment_without_stack_targets_unreachable_url():
    assert resolve_test_env({}, _no_stack) == (
        {**_LOCAL_DEFAULTS, "GRAMPS_API_URL": UNREACHABLE_API_URL},
        [],
    )


def test_inherited_password_alone_is_discarded():
    updates, ignored = resolve_test_env(
        {"GRAMPS_PASSWORD": "live-secret"}, _local_stack
    )
    assert (updates, ignored) == (_LOCAL_DEFAULTS, ["GRAMPS_PASSWORD"])


def test_local_url_with_half_set_credentials_falls_back_to_seed():
    env = {"GRAMPS_API_URL": LOCAL_URL, "GRAMPS_PASSWORD": "live-secret"}
    updates, ignored = resolve_test_env(env, _must_not_discover)
    assert (updates, ignored) == (
        {"GRAMPS_USERNAME": DEFAULT_USERNAME, "GRAMPS_PASSWORD": DEFAULT_PASSWORD},
        ["GRAMPS_PASSWORD"],
    )


def test_inherited_credentials_without_url_are_all_discarded():
    updates, ignored = resolve_test_env(
        {"GRAMPS_USERNAME": "fede", "GRAMPS_PASSWORD": "live-secret"}, _local_stack
    )
    assert (updates, ignored) == (
        _LOCAL_DEFAULTS,
        ["GRAMPS_USERNAME", "GRAMPS_PASSWORD"],
    )


def test_explicit_url_keeps_inherited_credentials():
    env = {
        "GRAMPS_API_URL": "https://gramps.example.org",
        "GRAMPS_USERNAME": "fede",
        "GRAMPS_PASSWORD": "live-secret",
    }
    assert resolve_test_env(env, _must_not_discover) == ({}, [])


def test_remote_url_with_half_set_credentials_is_not_completed():
    env = {"GRAMPS_API_URL": "https://gramps.example.org", "GRAMPS_USERNAME": "fede"}
    updates, ignored = resolve_test_env(env, _must_not_discover)
    assert (updates, ignored) == (
        {"GRAMPS_USERNAME": DEFAULT_USERNAME, "GRAMPS_PASSWORD": DEFAULT_PASSWORD},
        ["GRAMPS_USERNAME"],
    )


@pytest.mark.parametrize(
    ("port_output", "expected"),
    [
        ("127.0.0.1:54321\n", "http://127.0.0.1:54321"),
        ("0.0.0.0:5055", "http://0.0.0.0:5055"),
        ("", None),
        ("\n", None),
        (":0\n", None),
        ("127.0.0.1:not-a-port\n", None),
    ],
)
def test_parse_published_url(port_output, expected):
    assert parse_published_url(port_output) == expected


def test_resolve_base_url_keeps_explicit_url(monkeypatch):
    monkeypatch.setattr(_test_env, "local_api_url", _must_not_discover)
    assert (
        resolve_base_url("https://gramps.example.org") == "https://gramps.example.org"
    )


def test_resolve_base_url_discovers_own_stack(monkeypatch):
    monkeypatch.setattr(_test_env, "local_api_url", _local_stack)
    assert resolve_base_url(None) == LOCAL_URL


def test_resolve_base_url_without_stack_exits(monkeypatch):
    monkeypatch.setattr(_test_env, "local_api_url", _no_stack)
    with pytest.raises(SystemExit, match="make docker-up"):
        resolve_base_url(None)
