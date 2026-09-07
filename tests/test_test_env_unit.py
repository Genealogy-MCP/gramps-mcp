# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for the test-instance environment resolution."""

from tests._test_env import (
    DEFAULT_API_URL,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    resolve_test_env,
)

_LOCAL_DEFAULTS = {
    "GRAMPS_API_URL": DEFAULT_API_URL,
    "GRAMPS_USERNAME": DEFAULT_USERNAME,
    "GRAMPS_PASSWORD": DEFAULT_PASSWORD,
}


def test_empty_environment_gets_local_defaults():
    assert resolve_test_env({}) == (_LOCAL_DEFAULTS, [])


def test_inherited_password_alone_is_discarded():
    updates, ignored = resolve_test_env({"GRAMPS_PASSWORD": "live-secret"})
    assert (updates, ignored) == (_LOCAL_DEFAULTS, ["GRAMPS_PASSWORD"])


def test_inherited_credentials_without_url_are_all_discarded():
    updates, ignored = resolve_test_env(
        {"GRAMPS_USERNAME": "fede", "GRAMPS_PASSWORD": "live-secret"}
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
    assert resolve_test_env(env) == ({}, [])


def test_explicit_url_fills_only_missing_credentials():
    env = {"GRAMPS_API_URL": DEFAULT_API_URL, "GRAMPS_USERNAME": "seeder"}
    assert resolve_test_env(env) == ({"GRAMPS_PASSWORD": DEFAULT_PASSWORD}, [])
