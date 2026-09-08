# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Unit tests for the seed script's fixture row-count verification (issue #91)."""

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "seed_test_db",
    Path(__file__).resolve().parent.parent / "scripts" / "seed_test_db.py",
)
assert _SPEC and _SPEC.loader
seed_test_db = importlib.util.module_from_spec(_SPEC)
sys.modules["seed_test_db"] = seed_test_db
_SPEC.loader.exec_module(seed_test_db)

FIXTURE_COUNTS = seed_test_db.FIXTURE_COUNTS
count_shortfalls = seed_test_db.count_shortfalls


def test_full_import_has_no_shortfalls():
    """Exact fixture counts satisfy the floors."""
    assert count_shortfalls(dict(FIXTURE_COUNTS)) == []


def test_empty_tree_reports_every_collection():
    """An empty tree, the #91 failure mode, fails on all three collections."""
    observed = {name: 0 for name in FIXTURE_COUNTS}
    assert len(count_shortfalls(observed)) == len(FIXTURE_COUNTS)


def test_shortfall_line_names_observed_and_expected():
    """Failure lines print the observed count, not just 'verification failed'."""
    observed = dict(FIXTURE_COUNTS) | {"people": 3}
    assert count_shortfalls(observed) == [
        f"people: 3 rows, expected >= {FIXTURE_COUNTS['people']}"
    ]


def test_unavailable_count_is_a_shortfall():
    """A collection the API would not answer for fails closed."""
    observed = dict(FIXTURE_COUNTS) | {"sources": -1}
    assert count_shortfalls(observed) == [
        f"sources: count unavailable (expected {FIXTURE_COUNTS['sources']})"
    ]
