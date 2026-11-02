# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
MCP tool implementations, one module per feature.

Operations are registered in OPERATION_REGISTRY (operations.py). The
per-entity handlers live in ``SEARCH_HANDLERS`` (search_basic.py),
``GET_HANDLERS`` (search_details.py) and ``UPSERT_HANDLERS``
(upsert_table.py), keyed by entity type.
"""
