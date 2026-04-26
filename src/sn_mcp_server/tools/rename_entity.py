"""
Rename entity functions for SignNow MCP server.

Supports renaming: document, document_group, template, template_group.
"""

from __future__ import annotations

from typing import Literal

from signnow_client import SignNowAPIClient

from .models import RenameEntityResponse
from .utils import _detect_entity_type

_EntityType = Literal["document", "document_group", "template", "template_group"]


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
        entity_type: Entity type. Auto-detected via waterfall when None
            (document_group → template_group → template → document).
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        RenameEntityResponse with entity_id, entity_type, and new_name.

    Raises:
        ValueError: Unknown entity_type or entity not found.
    """
    allowed: tuple[str, ...] = ("document", "document_group", "template", "template_group")
    if entity_type is not None and entity_type not in allowed:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(allowed)}.")

    resolved_type: _EntityType = entity_type if entity_type is not None else _detect_entity_type(entity_id, token, client)

    if resolved_type == "document_group":
        client.rename_document_group(token, entity_id, new_name)
    elif resolved_type == "template_group":
        client.rename_template_group(token, entity_id, new_name)
    elif resolved_type in ("document", "template"):
        client.rename_document(token, entity_id, new_name)
    else:
        raise ValueError(f"Unsupported entity_type '{resolved_type}'")

    return RenameEntityResponse(entity_id=entity_id, entity_type=resolved_type, new_name=new_name)

