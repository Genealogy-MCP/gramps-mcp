# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""Parameters for the backup operations (create_backup, list_backups)."""

from pydantic import BaseModel, Field

LIST_BACKUPS_DEFAULT_LIMIT = 20
LIST_BACKUPS_MAX_LIMIT = 200


class CreateBackupParams(BaseModel):
    """Parameters for create_backup. The operation takes none."""

    # Reason: extra="forbid" (#95). An unknown key is a caller mistake, and
    # create_backup has no option it could have meant.
    model_config = {"extra": "forbid"}


class ListBackupsParams(BaseModel):
    """Parameters for list_backups."""

    # Reason: extra="forbid" (#95), see CreateBackupParams.
    model_config = {"extra": "forbid"}

    limit: int = Field(
        LIST_BACKUPS_DEFAULT_LIMIT,
        ge=1,
        le=LIST_BACKUPS_MAX_LIMIT,
        description=(
            "Maximum number of backups to return, newest first "
            f"(default: {LIST_BACKUPS_DEFAULT_LIMIT}, "
            f"range 1-{LIST_BACKUPS_MAX_LIMIT})"
        ),
    )
