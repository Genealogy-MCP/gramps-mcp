# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2025 cabout.me
# Copyright (C) 2026 Federico Castagnini

"""
JSON request bodies for Gramps Web API writes.

Turns a parsed params model into the body the client sends and pulls out
the MCP-side ``list_mode`` switch before it reaches Gramps.
"""

from typing import Any, Dict, Tuple

from pydantic import BaseModel

from .models.parameters.base_params import BaseDataModel


def _normalise_url_keys(json_data: dict) -> None:
    """
    Remap 'description' to 'desc' in any urls list, in-place.

    Gramps Web API stores URL description as 'desc'; callers historically pass
    'description'. This normalises both to 'desc' before the request is sent.
    """
    urls = json_data.get("urls")
    if not urls:
        return
    for url in urls:
        if isinstance(url, dict) and "description" in url and "desc" not in url:
            url["desc"] = url.pop("description")


def api_body(params: BaseModel) -> Tuple[Dict[str, Any], str]:
    """
    Turn a parsed write model into the JSON body and its list_mode.

    Write models serialise through ``to_api_payload()`` (the payload hook
    every ``BaseDataModel`` has); any other model is dumped as is.
    ``list_mode`` is an MCP-side switch Gramps does not know, so it is
    removed from every body, POST included, and returned for the PUT merge.

    Args:
        params (BaseModel): Parsed params model.

    Returns:
        Tuple[Dict[str, Any], str]: The body and the list mode
            (``"merge"`` when the model carries none).
    """
    if isinstance(params, BaseDataModel):
        body = params.to_api_payload()
    else:
        body = params.model_dump(exclude_none=True)
    list_mode = body.pop("list_mode", None) or "merge"
    _normalise_url_keys(body)
    return body, list_mode
