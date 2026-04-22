"""
Cancel invite functions for SignNow MCP server.

This module contains functions for cancelling active invites on documents and document groups
from the SignNow API.
"""

from __future__ import annotations

import time
from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import GetDocumentGroupResponse
from signnow_client.models.templates_and_documents import (
    CancelDocumentFieldInviteRequest,
    CancelDocumentFreeformInviteRequest,
    CancelFreeformInviteRequest,
    DocumentResponse,
)

from .models import CancelInviteResponse, CancelledInvite, InviteStatusSets


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
        - invite_type: 'field' | 'freeform' | None
        - status: 'pending' | 'completed' | 'no_invite'
        - pending_invite_ids: list of IDs to cancel
    """
    # Check field invites first
    if document_data.field_invites:
        pending_ids = []
        done_ids = []

        for field_invite in document_data.field_invites:
            normalized_status = field_invite.status.lower().replace(" ", "_")
            if normalized_status in InviteStatusSets.PENDING:
                pending_ids.append(field_invite.id)
            elif normalized_status in InviteStatusSets.DONE:
                done_ids.append(field_invite.id)

        if pending_ids:
            return ("field", "pending", pending_ids)

        if done_ids and len(done_ids) == len(document_data.field_invites):
            return (None, "completed", [])

    # Check freeform invites
    try:
        freeform_response = client.get_document_freeform_invites(token, document_id)
        if freeform_response.data:
            pending_ff_ids = []
            has_fulfilled = False

            for ff_invite in freeform_response.data:
                normalized_status = ff_invite.status.lower().replace(" ", "_")
                if normalized_status in InviteStatusSets.PENDING:
                    pending_ff_ids.append(ff_invite.id)
                elif normalized_status in InviteStatusSets.DONE:
                    has_fulfilled = True

            if pending_ff_ids:
                return ("freeform", "pending", pending_ff_ids)

            if has_fulfilled:
                return (None, "completed", [])
    except SignNowAPIError:
        # If freeform endpoint fails, treat as no freeform invites
        pass

    return (None, "no_invite", [])


def _cancel_document_invite(
    client: SignNowAPIClient,
    token: str,
    document_id: str,
    document_data: DocumentResponse,
    reason: str | None,
) -> CancelInviteResponse:
    """Cancel active invites on a single document.

    Resolves invite info, then cancels field or freeform invites as appropriate.
    Returns informational status if completed or no invite found.

    Args:
        client: SignNow API client.
        token: Bearer access token.
        document_id: Document ID.
        document_data: Pre-fetched DocumentResponse.
        reason: Optional cancellation reason.

    Returns:
        CancelInviteResponse with entity_type='document'.
    """
    invite_type, status, pending_ids = _resolve_document_invite_info(client, token, document_id, document_data)

    if status == "completed":
        return CancelInviteResponse(entity_id=document_id, entity_type="document", status="completed", cancelled_invite_ids=[])

    if status == "no_invite":
        return CancelInviteResponse(entity_id=document_id, entity_type="document", status="invite_not_sent", cancelled_invite_ids=[])

    cancelled_invites = []

    if invite_type == "field":
        # Cancel field invite
        cancel_reason = reason or "Cancelled by user"
        client.cancel_document_field_invite(token, document_id, CancelDocumentFieldInviteRequest(reason=cancel_reason))
        cancelled_invites = [CancelledInvite(id=invite_id, invite_type="field") for invite_id in pending_ids]

    elif invite_type == "freeform":
        # Cancel each freeform invite
        for invite_id in pending_ids:
            client.cancel_document_freeform_invite(token, invite_id, CancelDocumentFreeformInviteRequest(reason=reason))
        cancelled_invites = [CancelledInvite(id=invite_id, invite_type="freeform") for invite_id in pending_ids]

    return CancelInviteResponse(entity_id=document_id, entity_type="document", status="cancelled", cancelled_invite_ids=cancelled_invites)


def _resolve_document_group_invite_info(
    client: SignNowAPIClient,
    token: str,
    document_group_id: str,
    group_data: GetDocumentGroupResponse,
) -> tuple[str | None, str, list[str], str | None]:
    """Inspect a document group's invite state and determine invite type, status, and IDs.

    Checks freeform_invite first (from group_data), then field invite (via invite_id).
    For freeform: inspects per-document freeform invites to collect pending IDs.
    For field: queries get_field_invite to check status.

    Args:
        client: SignNow API client.
        token: Bearer access token.
        document_group_id: Document group ID.
        group_data: Pre-fetched GetDocumentGroupResponse.

    Returns:
        Tuple of (invite_type, status, pending_invite_ids, freeform_invite_id):
        - invite_type: 'field' | 'freeform' | None
        - status: 'pending' | 'completed' | 'no_invite'
        - pending_invite_ids: IDs for tracking in response
        - freeform_invite_id: doc-group-level freeform invite ID (for cancel endpoint)
    """
    # Check freeform invite first
    if group_data.freeform_invite and group_data.freeform_invite.id:
        freeform_invite_id = group_data.freeform_invite.id
        pending_ff_ids = []
        has_fulfilled = False

        # Inspect per-document freeform invites
        for doc in group_data.documents:
            try:
                ff_response = client.get_document_freeform_invites(token, doc.id)
                for ff_invite in ff_response.data:
                    normalized_status = ff_invite.status.lower().replace(" ", "_")
                    if normalized_status in InviteStatusSets.PENDING:
                        pending_ff_ids.append(ff_invite.id)
                    elif normalized_status in InviteStatusSets.DONE:
                        has_fulfilled = True
            except SignNowAPIError:
                # If per-document freeform check fails, skip this document
                continue

        if pending_ff_ids:
            return ("freeform", "pending", pending_ff_ids, freeform_invite_id)

        if has_fulfilled:
            return (None, "completed", [], None)

        return (None, "no_invite", [], None)

    # Check field invite
    if group_data.invite_id:
        try:
            field_invite_response = client.get_field_invite(token, document_group_id, group_data.invite_id)
            normalized_status = field_invite_response.status.lower().replace(" ", "_")

            if normalized_status in InviteStatusSets.DONE:
                return (None, "completed", [], None)

            if normalized_status in InviteStatusSets.PENDING:
                return ("field", "pending", [group_data.invite_id], None)

        except SignNowAPIError:
            # If field invite check fails, treat as no invite
            pass

    return (None, "no_invite", [], None)


def _cancel_document_group_invite(
    client: SignNowAPIClient,
    token: str,
    document_group_id: str,
    group_data: GetDocumentGroupResponse,
    reason: str | None,
) -> CancelInviteResponse:
    """Cancel active invites on a document group.

    Resolves invite info, then cancels freeform or field invites as appropriate.
    Returns informational status if completed or no invite found.

    Args:
        client: SignNow API client.
        token: Bearer access token.
        document_group_id: Document group ID.
        group_data: Pre-fetched GetDocumentGroupResponse.
        reason: Optional cancellation reason.

    Returns:
        CancelInviteResponse with entity_type='document_group'.
    """
    invite_type, status, pending_ids, freeform_invite_id = _resolve_document_group_invite_info(client, token, document_group_id, group_data)

    if status == "completed":
        return CancelInviteResponse(entity_id=document_group_id, entity_type="document_group", status="completed", cancelled_invite_ids=[])

    if status == "no_invite":
        return CancelInviteResponse(entity_id=document_group_id, entity_type="document_group", status="invite_not_sent", cancelled_invite_ids=[])

    cancelled_invites = []

    if invite_type == "freeform":
        # Cancel freeform invite at document group level
        cancel_request = CancelFreeformInviteRequest(reason=reason, client_timestamp=int(time.time()))
        client.cancel_freeform_invite(token, document_group_id, freeform_invite_id, cancel_request)
        cancelled_invites = [CancelledInvite(id=invite_id, invite_type="freeform") for invite_id in pending_ids]

    elif invite_type == "field":
        # Cancel field invite
        client.cancel_document_group_field_invite(token, document_group_id, pending_ids[0])
        cancelled_invites = [CancelledInvite(id=pending_ids[0], invite_type="field")]

    return CancelInviteResponse(entity_id=document_group_id, entity_type="document_group", status="cancelled", cancelled_invite_ids=cancelled_invites)


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
    # Validate entity_type if provided
    if entity_type is not None and entity_type not in ("document", "document_group"):
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'document' or 'document_group'.")

    # Auto-detect entity type if not provided
    doc_data = None
    group_data = None

    if entity_type is None:
        # Try document_group first (modern entity type)
        try:
            group_data = client.get_document_group(token, entity_id)
            entity_type = "document_group"
        except SignNowAPIError as e:
            if e.status_code == 404:
                # Try document second (legacy entity type)
                try:
                    doc_data = client.get_document(token, entity_id)
                    entity_type = "document"
                except SignNowAPIError as doc_err:
                    if doc_err.status_code == 404:
                        raise ValueError(f"Entity '{entity_id}' not found as document or document_group") from doc_err
                    # Non-404 errors propagate immediately
                    raise
            else:
                # Non-404 errors from document_group propagate immediately
                raise

    # Fetch entity data if not already fetched during auto-detection
    if entity_type == "document" and doc_data is None:
        doc_data = client.get_document(token, entity_id)
    elif entity_type == "document_group" and group_data is None:
        group_data = client.get_document_group(token, entity_id)

    # Dispatch to appropriate cancel path
    if entity_type == "document":
        return _cancel_document_invite(client, token, entity_id, doc_data, reason)
    else:  # entity_type == "document_group"
        return _cancel_document_group_invite(client, token, entity_id, group_data, reason)
