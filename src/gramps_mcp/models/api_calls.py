# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""
API calls enum for Gramps Web API endpoints.
"""

from enum import Enum


class ApiCalls(Enum):
    """Gramps Web API endpoints the handwritten operations call.

    Entity CRUD members mirror the resource table rows; the rest serve
    search_text, the analysis, backup and media-download operations and the
    typed-enum map lookup behind the GQL rewrite.
    """

    # PEOPLE operations
    GET_PEOPLE = ("GET", "people/")
    POST_PEOPLE = ("POST", "people/")
    GET_PERSON = ("GET", "people/{handle}")
    PUT_PERSON = ("PUT", "people/{handle}")
    DELETE_PERSON = ("DELETE", "people/{handle}")
    GET_PERSON_TIMELINE = ("GET", "people/{handle}/timeline")

    # FAMILIES operations
    GET_FAMILIES = ("GET", "families/")
    POST_FAMILIES = ("POST", "families/")
    GET_FAMILY = ("GET", "families/{handle}")
    PUT_FAMILY = ("PUT", "families/{handle}")
    DELETE_FAMILY = ("DELETE", "families/{handle}")
    GET_FAMILY_TIMELINE = ("GET", "families/{handle}/timeline")

    # EVENTS operations
    GET_EVENTS = ("GET", "events/")
    POST_EVENTS = ("POST", "events/")
    GET_EVENT = ("GET", "events/{handle}")
    PUT_EVENT = ("PUT", "events/{handle}")
    DELETE_EVENT = ("DELETE", "events/{handle}")

    # PLACES operations
    GET_PLACES = ("GET", "places/")
    POST_PLACES = ("POST", "places/")
    GET_PLACE = ("GET", "places/{handle}")
    PUT_PLACE = ("PUT", "places/{handle}")
    DELETE_PLACE = ("DELETE", "places/{handle}")

    # CITATIONS operations
    GET_CITATIONS = ("GET", "citations/")
    POST_CITATIONS = ("POST", "citations/")
    GET_CITATION = ("GET", "citations/{handle}")
    PUT_CITATION = ("PUT", "citations/{handle}")
    DELETE_CITATION = ("DELETE", "citations/{handle}")

    # SOURCES operations
    GET_SOURCES = ("GET", "sources/")
    POST_SOURCES = ("POST", "sources/")
    GET_SOURCE = ("GET", "sources/{handle}")
    PUT_SOURCE = ("PUT", "sources/{handle}")
    DELETE_SOURCE = ("DELETE", "sources/{handle}")

    # REPOSITORIES operations
    GET_REPOSITORIES = ("GET", "repositories/")
    POST_REPOSITORIES = ("POST", "repositories/")
    GET_REPOSITORY = ("GET", "repositories/{handle}")
    PUT_REPOSITORY = ("PUT", "repositories/{handle}")
    DELETE_REPOSITORY = ("DELETE", "repositories/{handle}")

    # MEDIA operations
    GET_MEDIA = ("GET", "media/")
    POST_MEDIA = ("POST", "media/")
    GET_MEDIA_ITEM = ("GET", "media/{handle}")
    PUT_MEDIA_ITEM = ("PUT", "media/{handle}")
    DELETE_MEDIA_ITEM = ("DELETE", "media/{handle}")

    # NOTES operations
    GET_NOTES = ("GET", "notes/")
    POST_NOTES = ("POST", "notes/")
    GET_NOTE = ("GET", "notes/{handle}")
    PUT_NOTE = ("PUT", "notes/{handle}")
    DELETE_NOTE = ("DELETE", "notes/{handle}")

    # TAGS operations
    GET_TAGS = ("GET", "tags/")
    POST_TAGS = ("POST", "tags/")
    GET_TAG = ("GET", "tags/{handle}")
    PUT_TAG = ("PUT", "tags/{handle}")
    DELETE_TAG = ("DELETE", "tags/{handle}")

    # SEARCH operations
    GET_SEARCH = ("GET", "search/")

    # MANAGEMENT operations - Transactions
    GET_TRANSACTIONS_HISTORY = ("GET", "transactions/history/")

    # MANAGEMENT operations - Types
    GET_TYPES_DEFAULT_MAP = ("GET", "types/default/{datatype}/map")
    GET_TYPES_CUSTOM_DATATYPE = ("GET", "types/custom/{datatype}")

    # REPORTS operations
    GET_REPORT_FILE = ("GET", "reports/{report_id}/file")
    POST_REPORT_FILE = ("POST", "reports/{report_id}/file")
    GET_REPORT_PROCESSED = ("GET", "reports/{report_id}/file/processed/{filename}")

    # BACKUPS operations (gramps-webapi 3.24+)
    GET_BACKUPS = ("GET", "backups/")
    POST_BACKUPS = ("POST", "backups/")

    # METADATA operations
    GET_METADATA = ("GET", "metadata/")

    # TREES operations
    GET_TREES = ("GET", "trees/")
    GET_TREE = ("GET", "trees/{tree_id}")

    @property
    def method(self) -> str:
        """Get HTTP method for this API call."""
        return self.value[0]

    @property
    def endpoint(self) -> str:
        """Get endpoint path for this API call."""
        return self.value[1]
