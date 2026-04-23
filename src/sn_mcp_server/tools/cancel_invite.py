"""
Cancel invite functions for SignNow MCP server.

This module contains functions for cancelling active invites on documents and document groups
from the SignNow API.
"""

from __future__ import annotations

import time
from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIHTTPError
from signnow_client.models.document_groups import DocumentGroupV2Data, GetDocumentGroupV2Response
from signnow_client.models.templates_and_documents import (
    CancelDocumentFieldInviteRequest,
    CancelDocumentFreeformInviteRequest,
    CancelFreeformInviteRequest,
    DocumentResponse,
)
from sn_mcp_server.tools.create_template import _is_not_found_error

from .models import CancelInviteResponse, InviteStatusSets, InviteStatusValues


def _resolve_document_invite_info(
    client: SignNowAPIClient,
    token: str,
    document_id: str,
    document_data: DocumentResponse,
) -> tuple[str | None, str, list[str]]:
    """Inspect a document's invite state and determine invite type, status, and pending IDs.

    Checks field_invites first (from document_data), then freeform invites (via API call).
    Uses InviteStatusSets for status normalization.

    Args:
        client: SignNow API client.
        token: Bearer access token.
        document_id: Document ID.
        document_data: Pre-fetched DocumentResponse.

    Returns:
        Tuple of (invite_type, status, pending_invite_ids):
        - invite_type: 'field' | 'freeform' | 'embedded' | None
        - status: 'pending' | 'completed' | 'no_invite'
        - pending_invite_ids: list of IDs to cancel
    """
    pending_ids = []
    done_ids = []
    invites = document_data.field_invites or client.get_document_freeform_invites(token, document_id).data
    invite_type = "field" if document_data.field_invites else "freeform"

    # Detect embedded invites: if any field invite has is_embedded=True, treat as embedded
    if document_data.field_invites and any(getattr(inv, "is_embedded", False) for inv in document_data.field_invites):
        invite_type = "embedded"

    for invite in invites:
        normalized_status = InviteStatusValues.from_raw_status(invite.status)
        if normalized_status in InviteStatusSets.PENDING:
            pending_ids.append(invite.id)
        elif normalized_status in InviteStatusSets.DONE:
            done_ids.append(invite.id)

    if pending_ids:
        return (invite_type, "pending", pending_ids)

    if document_data.field_invites and done_ids and len(done_ids) == len(document_data.field_invites):
        return (None, "completed", [])

    if done_ids and len(done_ids) > 0:
        return (None, "completed", [])

    return (None, "no_invite", [])


def _resolve_document_group_invite_info(
    client: SignNowAPIClient,
    token: str,
    document_group_id: str,
    group_data: DocumentGroupV2Data,
) -> tuple[str | None, str, list[str]]:
    """Inspect a document group's invite state and determine invite type, status, and IDs.

    Checks freeform_invite first (from group_data), then field invite (via invite_id).
    For field invites, queries get_field_invite to check is_embedded status.

    Args:
        client: SignNow API client.
        token: Bearer access token.
        document_group_id: Document group ID.
        group_data: Pre-fetched DocumentGroupV2Data.

    Returns:
        Tuple of (invite_type, status, pending_invite_ids):
        - invite_type: 'field' | 'freeform' | 'embedded' | None
        - status: 'pending' | 'completed' | 'no_invite'
        - pending_invite_ids: IDs for tracking in response
    """

    normalized_status = InviteStatusValues.from_raw_status(group_data.state)
    if (normalized_status in InviteStatusSets.CREATED) or (normalized_status in InviteStatusSets.DECLINED):
        return (None, "no_invite", [])
    elif normalized_status in InviteStatusSets.DONE:
        return (None, "completed", [])
    elif normalized_status in InviteStatusSets.PENDING and group_data.invite_id:
        # Check if the field invite is an embedded invite via the group invite API
        field_invite_response = client.get_field_invite(token, document_group_id, group_data.invite_id)
        if getattr(field_invite_response.invite, "is_embedded", False):
            return ("embedded", "pending", [group_data.invite_id])
        return ("field", "pending", [group_data.invite_id])
    elif normalized_status in InviteStatusSets.PENDING and group_data.freeform_invite and group_data.freeform_invite.id:
        return ("freeform", "pending", [group_data.freeform_invite.id])

    return (None, "no_invite", [])


def _resolve_entity_type(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
) -> tuple[Literal["document", "document_group"], DocumentResponse | GetDocumentGroupV2Response]:
    """Phase A: Resolve entity type and fetch entity data.

    Auto-detection order: document_group first, document second (per AGENTS.md).
    """

    if entity_type is not None and entity_type not in ("document", "document_group"):
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'document' or 'document_group'.")

    if entity_type == "document":
        return ("document", client.get_document(token, entity_id))

    if entity_type == "document_group":
        return ("document_group", client.get_document_group_v2(token, entity_id))

    try:
        return ("document_group", client.get_document_group_v2(token, entity_id))
    except SignNowAPIHTTPError as exc:
        if exc.status_code != 404 and not _is_not_found_error(exc):
            raise
    try:
        document = client.get_document(token, entity_id)
        if not document.template:
            return ("document", document)
        raise ValueError(f"Entity '{entity_id}' is a template, not a document")
    except Exception:
        raise ValueError(f"Entity '{entity_id}' not found as document group or document") from None


def _cancel_invite(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    reason: str | None,
    token: str,
    client: SignNowAPIClient,
) -> CancelInviteResponse:
    """Main dispatcher: cancel active invites on a document or document group.

    Auto-detects entity type when not provided (document_group first, document second).
    Fetches entity data, then delegates to document or document_group cancel path.

    Args:
        entity_id: Document or document group ID.
        entity_type: Optional discriminator. Auto-detected if None.
        reason: Optional cancellation reason forwarded to SignNow API.
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        CancelInviteResponse.

    Raises:
        ValueError: Invalid entity_type or entity not found during auto-detection.
    """

    (entity_type, entity) = _resolve_entity_type(client, token, entity_id, entity_type)

    invite_type: str | None = None
    status: str | None = None
    pending_ids: list[str] = []
    if entity_type == "document_group" and isinstance(entity, GetDocumentGroupV2Response):
        invite_type, status, pending_ids = _resolve_document_group_invite_info(client, token, entity_id, entity.data)
    elif isinstance(entity, DocumentResponse):
        invite_type, status, pending_ids = _resolve_document_invite_info(client, token, entity_id, entity)

    if status == "completed":
        return CancelInviteResponse(entity_id=entity_id, entity_type=entity_type, status="completed", cancelled_invite_ids=[])
    elif status == "no_invite":
        return CancelInviteResponse(entity_id=entity_id, entity_type=entity_type, status="invite_not_sent", cancelled_invite_ids=[])

    if entity_type == "document" and invite_type == "embedded":
        client.delete_document_embedded_invites(token, entity_id)
    elif entity_type == "document_group" and invite_type == "embedded":
        client.delete_document_group_embedded_invites(token, entity_id)
    elif entity_type == "document" and invite_type == "field":
        client.cancel_document_field_invite(token, entity_id, CancelDocumentFieldInviteRequest(reason=reason))
    elif entity_type == "document" and invite_type == "freeform":
        for invite_id in pending_ids:
            client.cancel_document_freeform_invite(token, invite_id, CancelDocumentFreeformInviteRequest(reason=reason))
    elif entity_type == "document_group" and invite_type == "field":
        client.cancel_document_group_field_invite(token, entity_id, pending_ids[0])
    elif entity_type == "document_group" and invite_type == "freeform":
        client.cancel_freeform_invite(token, entity_id, pending_ids[0], CancelFreeformInviteRequest(reason=reason, client_timestamp=int(time.time())))

    return CancelInviteResponse(entity_id=entity_id, entity_type=entity_type, status="cancelled", cancelled_invite_ids=pending_ids, cancelled_invite_type=invite_type)
