# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
Simplified parameter models for reduced token usage.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Searchable entity types in Gramps (excludes TAG — tags use list_tags)."""

    PERSON = "person"
    FAMILY = "family"
    EVENT = "event"
    PLACE = "place"
    SOURCE = "source"
    CITATION = "citation"
    MEDIA = "media"
    REPOSITORY = "repository"
    NOTE = "note"


class DeletableEntityType(str, Enum):
    """All entity types that can be deleted (includes TAG)."""

    PERSON = "person"
    FAMILY = "family"
    EVENT = "event"
    PLACE = "place"
    SOURCE = "source"
    CITATION = "citation"
    MEDIA = "media"
    REPOSITORY = "repository"
    NOTE = "note"
    TAG = "tag"


class SimpleFindParams(BaseModel):
    """Simplified parameters for type-based search."""

    model_config = {"extra": "forbid"}

    type: EntityType = Field(description="Entity type to search")
    gql: str = Field(
        description=(
            "Gramps Query Language filter. "
            'Multi-word values MUST be quoted: name.value ~ "New York". '
            "Property paths vary by type -- read gql://documentation resource."
        )
    )
    max_results: int = Field(default=20, description="Maximum results to return")


class SimpleSearchParams(BaseModel):
    """Simplified parameters for full-text search."""

    query: str = Field(description="Plain text search query")
    max_results: int = Field(default=20, description="Maximum results to return")


class SimpleGetParams(BaseModel):
    """Simplified parameters for getting entity details."""

    type: EntityType = Field(
        description=(
            "Entity type: person, family, event, place, source, "
            "citation, media, repository, note"
        )
    )
    handle: Optional[str] = Field(default=None, description="Entity handle")
    gramps_id: Optional[str] = Field(
        default=None, description="Gramps ID (e.g., I0001 or F0001)"
    )


class DeleteParams(BaseModel):
    """Parameters for deleting an entity."""

    type: DeletableEntityType = Field(description="Entity type to delete")
    handle: str = Field(description="Handle of the entity to delete")
