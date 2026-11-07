# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""
Parameters for transactions endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field


class TransactionHistoryParams(BaseModel):
    """
    Parameters for getting transaction history.

    Args:
        old (Optional[bool]): Whether to include the raw object data before the
            change
        new (Optional[bool]): Whether to include the raw object data after the
            change
        page (int): Page number representing a subset of results to be
            returned
        pagesize (int): The number of items that constitute a page
        sort (Optional[str]): Sort the transactions. Can be 'id' to sort
            ascending, '-id' to sort descending
        before (Optional[float]): Unix timestamp. Only return transactions
            committed before this time
        after (Optional[float]): Unix timestamp. Only return transactions
            committed after this time

    Returns:
        Dict[str, Any]: List of transaction history
    """

    # Reason: extra="forbid" (#95). An LLM fills this in; an unknown key is a
    # caller mistake and must not be dropped in silence.
    model_config = {"extra": "forbid"}

    old: Optional[bool] = Field(
        None, description="Whether to include the raw object data before the change"
    )
    new: Optional[bool] = Field(
        None, description="Whether to include the raw object data after the change"
    )
    # Reason: not Optional (#140). Gramps Web applies a limit only when page and
    # pagesize are both sent. A missing page returns the entire history.
    page: int = Field(
        1,
        ge=1,
        description=(
            "Page number (1-based) representing a subset of results to be returned."
            " Defaults to 1"
        ),
    )
    pagesize: int = Field(
        20,
        ge=1,
        le=100,
        description="The number of items that constitute a page. Defaults to 20, "
        "maximum 100",
    )
    sort: Optional[str] = Field(
        None,
        description="Sort the transactions. Can be 'id' to sort ascending, "
        "'-id' to sort descending",
    )
    before: Optional[float] = Field(
        None,
        description="Unix timestamp. Only return transactions committed before "
        "this time",
    )
    after: Optional[float] = Field(
        None,
        description="Unix timestamp. Only return transactions committed after "
        "this time",
    )
