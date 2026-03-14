# gramps-mcp - AI-Powered Genealogy Research & Management
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Pydantic models for media-related operations.

API calls supported in this category:
- GET_MEDIA: Get information about multiple media items
- POST_MEDIA: Add a new media file to the database
- GET_MEDIA_ITEM: Get information about a specific media item
- PUT_MEDIA_ITEM: Update the media object
- DELETE_MEDIA_ITEM: Delete the media object
- GET_MEDIA_FILE: Download a specific media item
- PUT_MEDIA_FILE: Update an existing media object's file
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base_params import BaseDataModel, BaseGetMultipleParams


class MediaSearchParams(BaseGetMultipleParams):
    """Parameters for searching media items."""

    dates: Optional[str] = Field(None, description="Date filter for media items")
    filemissing: Optional[bool] = Field(
        None, description="Only return media where file is missing"
    )


class MediaFileParams(BaseModel):
    """Parameters for media file operations."""

    handle: str = Field(..., min_length=8, description="Media handle identifier")
    uploadmissing: Optional[bool] = Field(
        None, description="Upload missing file to existing media object"
    )


class MediaSaveParams(BaseDataModel):
    """Parameters for creating or updating a media item."""

    desc: str = Field(
        ...,
        description=(
            "Human-readable label for this media record (e.g. 'Birth certificate 1878')"
        ),
    )
    file_location: Optional[str] = Field(
        None,
        description=(
            "Absolute local file path to upload (e.g. '/home/user/photo.jpg'). "
            "Required when creating new media (no handle provided). "
            "Omit when updating an existing media record. "
            "This is the upload source, not the Gramps-relative storage path."
        ),
    )
    path: Optional[str] = Field(
        None,
        min_length=1,
        description=(
            "Gramps-relative storage path assigned after upload "
            "(e.g. 'photos/photo.jpg'). Leave unset when creating — "
            "Gramps assigns this automatically."
        ),
    )
    mime: Optional[str] = Field(
        None,
        description=(
            "MIME type of the media file (e.g. 'image/jpeg'). "
            "Auto-detected from file_location when omitted."
        ),
    )
    citation_list: Optional[List[str]] = Field(
        None, description="List of citation handles"
    )
    date: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Date object with dateval array [day, month, year, False], quality "
            "(0=regular, 1=estimated, 2=calculated), and modifier (0=regular, "
            "1=before, 2=after, 3=about, 4=range, 5=span, 6=textonly, 7=from, 8=to)"
        ),
    )
