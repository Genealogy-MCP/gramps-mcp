# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Unit tests for the gql_private_reject pure detector.

Network-free (MCP-25). The detector blocks GQL queries that filter the
`private` field with a boolean literal -- a syntax the Gramps engine
silently returns empty for, falsely reading as "no private records".
"""

import pytest

from src.gramps_mcp.tools._gql_hints import gql_private_reject

# Boolean-literal comparisons on `private` that must be rejected.
_REJECTED = [
    "private = True",
    "private = False",
    "private != True",
    "private != False",
    "private=True",
    "private  =  false",
    "PRIVATE = TRUE",
    "private != tRuE",
    "media_list.length > 0 and private = True",
]

# Queries that must pass (empty return = no reject).
_ALLOWED = [
    "private = 1",
    "private = 0",
    "private",
    "active = True",
    "confirmed != False",
    "name.value ~ Boston",
    "",
]


class TestGqlPrivateReject:
    @pytest.mark.parametrize("gql", _REJECTED)
    def test_rejects_boolean_literal(self, gql):
        assert gql_private_reject(gql) != ""

    @pytest.mark.parametrize("gql", _ALLOWED)
    def test_allows_valid(self, gql):
        assert gql_private_reject(gql) == ""

    def test_message_is_actionable(self):
        msg = gql_private_reject("private = True")
        # MCP-9: point the caller at a syntax that actually works.
        assert "private = 1" in msg or "`private`" in msg
