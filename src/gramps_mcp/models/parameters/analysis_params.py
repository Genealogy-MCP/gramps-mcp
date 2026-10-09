# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Parameters for the analysis operations (tree stats, ancestors, descendants)."""

from typing import Optional

from pydantic import BaseModel, Field

_GENERATIONS_DESCRIPTION = (
    "Max generations to retrieve (default: 5, use higher values "
    "carefully as they can overflow context)"
)


class TreeInfoParams(BaseModel):
    """Parameters for get_tree_stats."""

    # Reason: extra="forbid" (#95). An analysis parameter is a command an LLM
    # wrote; an unknown key is a caller mistake and must not be dropped.
    model_config = {"extra": "forbid"}

    include_statistics: bool = Field(True, description="Include statistics")


class DescendantsParams(BaseModel):
    """Parameters for get_descendants."""

    # Reason: extra="forbid" (#95), see TreeInfoParams.
    model_config = {"extra": "forbid"}

    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(5, description=_GENERATIONS_DESCRIPTION)


class AncestorsParams(BaseModel):
    """Parameters for get_ancestors."""

    # Reason: extra="forbid" (#95), see TreeInfoParams.
    model_config = {"extra": "forbid"}

    gramps_id: str = Field(..., description="Person ID")
    max_generations: Optional[int] = Field(5, description=_GENERATIONS_DESCRIPTION)
