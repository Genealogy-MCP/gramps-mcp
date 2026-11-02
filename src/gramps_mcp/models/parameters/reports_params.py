# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me

"""
Parameters for reports endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ReportFileParams(BaseModel):
    """
    Parameters for getting a specific report file.

    Args:
        report_id (str): ID of the report to get
        options (Optional[str]): Report options in JSON format

    Returns:
        Any: Report file content
    """

    options: Optional[str] = Field(None, description="Report options in JSON format")
