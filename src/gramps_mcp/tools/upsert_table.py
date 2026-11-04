# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Federico Castagnini

"""
Generic table-driven upsert handler (#102, #103; slices S3 and S4 of #99).

Every writable entity saves through ``upsert_entity``. The entity's
``WriteBinding`` (``write_overlays.WRITE_BINDINGS``) names the hand model
and hooks; the resource table row names the paths. The order is fixed:
parse, reference checks, media upload, then the write (the client does
the merge-mode GET and merge before a PUT). Nothing is written before
every reference check passes.

Reason: the upload runs before the write because on media create the
upload is what makes the record; the metadata write is then a PUT on the
handle it returns. On media update the stored file is replaced first.

A create POSTs under a handle chosen here (#106). Gramps Web commits the
record before it updates the search index and usage counts, and answers
5xx when that later step fails. The known handle lets one GET tell a
landed write from a lost one, so a caller never retries into a duplicate.
A POST that times out after it was sent gets the same check (#130), but
a missing record then proves nothing: the server may still be saving it.
A media create cannot choose its handle; ``write_hooks.upload_media``
checks a failed upload by file checksum instead, and a failed metadata PUT
names the uploaded record so a retry updates it (#131).
"""

import logging
import uuid
from collections.abc import Callable, Coroutine, Mapping
from typing import Any, List

from mcp.types import TextContent

from ..auth import GrampsAuthError
from ..client import GrampsAPIError, GrampsWebAPIClient, get_client
from ..config import get_settings
from ..resource_rows import EntityResource
from ..resource_table import ENTITY_RESOURCES
from ..write_overlays import WRITE_BINDINGS, WriteBinding, write_row
from ._compat import extract_arguments
from ._data_helpers import _extract_entity_data, _format_save_response
from ._errors import McpToolError, parse_params, raise_tool_error

logger = logging.getLogger(__name__)

UpsertHandler = Callable[..., Coroutine[Any, Any, List[TextContent]]]


async def upsert_entity(
    entity: str,
    arguments: Any,
    bindings: Mapping[str, WriteBinding] = WRITE_BINDINGS,
    table: Mapping[str, EntityResource] = ENTITY_RESOURCES,
) -> List[TextContent]:
    """
    Create or update one record of a table-driven entity.

    Args:
        entity (str): Entity key bound in ``bindings``.
        arguments (Any): Raw arguments dict, or an already parsed model.
        bindings (Mapping[str, WriteBinding]): Per-entity write bindings.
        table (Mapping[str, EntityResource]): Resource rows.

    Returns:
        List[TextContent]: The formatted save confirmation.

    Raises:
        McpToolError: Invalid arguments, a failed reference check, or a
            failed API call (with "<entity> save" context).
    """
    binding = bindings[entity]
    try:
        if not arguments and binding.empty_arguments_error:
            raise ValueError(binding.empty_arguments_error)
        # Reason: the hand model is the only parse boundary; the table's
        # field set never filters, adds or forwards a field.
        validated: Any = (
            arguments
            if isinstance(arguments, binding.model)
            else parse_params(
                binding.model, arguments if isinstance(arguments, dict) else {}
            )
        )
        row = write_row(entity, table)
        tree_id = get_settings().gramps_tree_id

        client = get_client()
        for check in binding.reference_checks:
            await check(client, tree_id, validated)

        uploaded = (
            await binding.media_upload(client, tree_id, validated)
            if binding.media_upload is not None
            else None
        )

        if validated.handle:
            result = await client.call_resource(
                "PUT",
                row.item_path,
                validated,
                tree_id=tree_id,
                handle=validated.handle,
            )
            operation = "updated"
        elif uploaded:
            result = await _save_uploaded(
                client, entity, row, validated, tree_id, uploaded
            )
            operation = "created"
        else:
            result = await _create(client, entity, row, validated, tree_id)
            operation = "created"

        nudge = (
            binding.nudge_citation
            and operation == "created"
            and not getattr(validated, "citation_list", None)
        )
        entity_data = _extract_entity_data(result, entity)
        if binding.format_response is not None:
            text = binding.format_response(entity_data, operation)
        else:
            text = await _format_save_response(
                client, entity_data, entity, operation, tree_id, nudge
            )
        return [TextContent(type="text", text=text)]

    except McpToolError:
        raise
    except Exception as e:
        raise_tool_error(e, f"{entity} save")


async def _create(
    client: GrampsWebAPIClient,
    entity: str,
    row: EntityResource,
    validated: Any,
    tree_id: str,
) -> Any:
    """
    POST a new record under a fresh handle; check it on an unknown outcome.

    The outcome is unknown when the POST answered 5xx or timed out after
    it was sent. A 4xx or a request that never left raises as is.

    Args:
        client (GrampsWebAPIClient): Session-wide API client.
        entity (str): Entity key, for the error text.
        row (EntityResource): The entity's resource row.
        validated (Any): Parsed write model without a handle.
        tree_id (str): Family tree identifier.

    Returns:
        Any: The POST response, or the stored record when the POST
            answered 5xx or timed out after the write landed.

    Raises:
        GrampsAPIError: The POST failed; on an unknown outcome the message
            says whether the record was written.
    """
    handle = uuid.uuid4().hex
    try:
        return await client.call_resource(
            "POST",
            row.collection_path,
            validated,
            tree_id=tree_id,
            handle=handle,
        )
    except GrampsAPIError as error:
        status = error.status_code
        if not error.request_sent or (status is not None and status < 500):
            raise
        try:
            stored = await client.call_resource(
                "GET", row.item_path, tree_id=tree_id, handle=handle
            )
        except (GrampsAPIError, GrampsAuthError) as check:
            missing = isinstance(check, GrampsAPIError) and check.status_code == 404
            if missing and status is None:
                raise GrampsAPIError(
                    f"{error} No {entity} has handle `{handle}` yet, but the "
                    f"server may still be saving it. Get handle `{handle}` "
                    "before retrying, so a retry makes no duplicate.",
                    request_sent=True,
                ) from error
            if missing:
                raise GrampsAPIError(
                    f"{error} Nothing was written: no {entity} has handle "
                    f"`{handle}`, so a retry makes no duplicate.",
                    status_code=error.status_code,
                ) from error
            raise GrampsAPIError(
                f"{error} The {entity} may have been written. Get handle "
                f"`{handle}` before retrying, so a retry makes no duplicate.",
                status_code=error.status_code,
                request_sent=True,
            ) from error
        logger.warning(
            f"{entity} create failed ({error}) but the record with handle "
            f"{handle} is stored; reporting it as created"
        )
        return stored


async def _save_uploaded(
    client: GrampsWebAPIClient,
    entity: str,
    row: EntityResource,
    validated: Any,
    tree_id: str,
    handle: str,
) -> Any:
    """
    PUT the fields of a new record onto the handle its upload created.

    Args:
        client (GrampsWebAPIClient): Session-wide API client.
        entity (str): Entity key, for the error text.
        row (EntityResource): The entity's resource row.
        validated (Any): Parsed write model without a handle.
        tree_id (str): Family tree identifier.
        handle (str): Handle of the record the upload created.

    Returns:
        Any: The PUT response.

    Raises:
        GrampsAPIError: The PUT failed; the message names the stored
            record so a retry updates it instead of uploading again (#131).
    """
    try:
        return await client.call_resource(
            "PUT", row.item_path, validated, tree_id=tree_id, handle=handle
        )
    except GrampsAPIError as error:
        raise GrampsAPIError(
            f"{error} The {entity} file is stored as handle `{handle}`, but "
            "its fields may not be saved. Retry with handle "
            f"`{handle}` to update that record, so a retry makes no duplicate.",
            status_code=error.status_code,
            request_sent=error.request_sent,
        ) from error


def make_upsert_handler(entity: str) -> UpsertHandler:
    """
    Build the ``(ctx, params)`` operation handler for one entity.

    Args:
        entity (str): Entity key bound in ``WRITE_BINDINGS``.

    Returns:
        UpsertHandler: Async handler the execute meta-tool dispatches to.
    """

    async def handler(ctx: Any = None, params: Any = None) -> List[TextContent]:
        """
        Create or update one record through the generic upsert.

        Args:
            ctx (Any): Operation context, or legacy arguments dict.
            params (Any): Arguments dict or parsed model.

        Returns:
            List[TextContent]: The formatted save confirmation.
        """
        return await upsert_entity(entity, extract_arguments(ctx, params))

    handler.__name__ = f"upsert_{entity}_tool"
    handler.__qualname__ = handler.__name__
    return handler


UPSERT_HANDLERS: dict[str, UpsertHandler] = {
    entity: make_upsert_handler(entity) for entity in WRITE_BINDINGS
}
