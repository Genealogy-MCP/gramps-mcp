# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Pinned gramps-webapi version of the checked-in OpenAPI snapshot.

The snapshot under `schema/` describes exactly this gramps-webapi release.
`make schema-fetch` refuses to overwrite the snapshot from a server that
reports a different version unless told to, and startup logs one warning
when the live server differs. A unit test asserts this pin equals the
version the sidecar records.
"""

SCHEMA_VERSION = "3.24.0"
