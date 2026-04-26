"""
Rename entity functions for SignNow MCP server.

Supports renaming: document, document_group, template, template_group.
"""

from __future__ import annotations

from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIHTTPError

from .create_template import _is_not_found_error
from .models import RenameEntityResponse

_EntityType = Literal["document", "document_group", "template", "template_group"]


def _auto_detect_entity_type(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
) -> _EntityType:
    """Auto-detect entity type from entity_id.

    Detection order (per AGENTS.md document_group first):
    1. document_group  — GET /v2/document-groups/{id}
    2. template        — GET /document/{id}, check template flag
    3. document        — GET /document/{id}, no template flag
    template_group cannot be auto-detected; must be passed explicitly.

    Args:
        client: SignNow API client.
        token: Bearer access token.
        entity_id: ID to detect.

    Returns:
        Detected entity type.

    Raises:
        ValueError: Entity not found or unsupported type.
    """
    try:
        client.get_document_group_v2(token, entity_id)
        return "document_group"
    except SignNowAPIHTTPError as exc:
        if exc.status_code != 404 and not _is_not_found_error(exc):
            raise

    try:
        doc = client.get_document(token, entity_id)
        return "template" if doc.template else "document"
    except SignNowAPIHTTPError as exc:
        if exc.status_code != 404 and not _is_not_found_error(exc):
            raise

    raise ValueError(f"Entity '{entity_id}' not found as document_group, template, or document. To rename a template_group, pass entity_type='template_group' explicitly.")


def _rename_entity(
    entity_id: str,
    new_name: str,
    entity_type: _EntityType | None,
    token: str,
    client: SignNowAPIClient,
) -> RenameEntityResponse:
    """Rename a document, document_group, template, or template_group.

    Args:
        entity_id: ID of the entity to rename.
        new_name: New name to apply.
        entity_type: Entity type. Required for template_group; auto-detected otherwise.
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        RenameEntityResponse with entity_id, entity_type, and new_name.

    Raises:
        ValueError: Unknown entity_type, entity not found, or template_group without explicit type.
    """
    allowed: tuple[str, ...] = ("document", "document_group", "template", "template_group")
    if entity_type is not None and entity_type not in allowed:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(allowed)}.")

    resolved_type: _EntityType
    if entity_type is None:
        resolved_type = _auto_detect_entity_type(client, token, entity_id)
    else:
        resolved_type = entity_type

    if resolved_type == "document_group":
        client.rename_document_group(token, entity_id, new_name)
    elif resolved_type == "template_group":
        client.rename_template_group(token, entity_id, new_name)
    elif resolved_type in ("document", "template"):
        client.rename_document(token, entity_id, new_name)
    else:
        raise ValueError(f"Unsupported entity_type '{resolved_type}'")

    return RenameEntityResponse(entity_id=entity_id, entity_type=resolved_type, new_name=new_name)
