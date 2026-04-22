"""
Update invite recipient functions for SignNow MCP server.

Replaces the signing recipient on a pending field invite for a document.
Implements the three-step SignNow replace-signer flow:
1. Delete the field invite for the current signer
2. Replace with a new signer via POST /field_invite
3. Trigger the invite to send to the new signer
"""

from __future__ import annotations

from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.models.templates_and_documents import (
    DocumentFieldInviteStatus,
    DocumentResponse,
    ReplaceFieldInviteRequest,
)

from .cancel_invite import _resolve_entity_type
from .models import InviteStatusValues, UpdateInviteRecipientResponse

_PENDING_STATUSES = {InviteStatusValues.PENDING, InviteStatusValues.CREATED}


def _find_pending_invite_for_email(
    document: DocumentResponse,
    current_email: str,
    role: str | None,
) -> DocumentFieldInviteStatus | None:
    """Find a pending/created field invite matching the given email (and optional role).

    Args:
        document: Pre-fetched DocumentResponse with field_invites.
        current_email: Email of the current signer to match.
        role: Optional role name filter for multi-role documents.

    Returns:
        The matching DocumentFieldInviteStatus, or None if not found.
    """
    for invite in document.field_invites:
        normalized_status = InviteStatusValues.from_raw_status(invite.status)
        if normalized_status not in _PENDING_STATUSES:
            continue
        if invite.email.lower() != current_email.lower():
            continue
        if role is not None and invite.role.lower() != role.lower():
            continue
        return invite
    return None


def _update_invite_recipient(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    current_email: str,
    new_email: str,
    role: str | None,
    expiration_days: int | None,
    decline_by_signature: int | None,
    reminder: int | None,
    authentication_type: str | None,
    password: str | None,
    phone: str | None,
    token: str,
    client: SignNowAPIClient,
) -> UpdateInviteRecipientResponse:
    """Replace the signing recipient on a pending field invite.

    Implements the three-step SignNow replace-signer flow (document only):
    1. Resolve entity type and fetch document data
    2. Find pending invite matching current_email
    3. Delete → Replace → Trigger

    For document_group entities, raises NotImplementedError.

    Args:
        entity_id: Document or document group ID.
        entity_type: Optional entity type discriminator. Auto-detected if None.
        current_email: Email of the current signer to replace.
        new_email: Email of the new signer.
        role: Optional role filter for multi-role documents.
        expiration_days: Optional days until invite expires (max 30).
        decline_by_signature: Optional decline button setting (0 or 1).
        reminder: Optional reminder days (max 30).
        authentication_type: Optional identity verification type ('password' or 'phone').
        password: Optional password for identity verification.
        phone: Optional phone number for identity verification.
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        UpdateInviteRecipientResponse.

    Raises:
        NotImplementedError: When entity is a document_group.
        ValueError: When no pending invite is found for current_email.
    """
    resolved_type, entity = _resolve_entity_type(client, token, entity_id, entity_type)

    if resolved_type == "document_group":
        raise NotImplementedError(
            f"update_invite_recipient is not yet implemented for document groups (entity '{entity_id}'). "
            "Only individual documents are supported."
        )

    document: DocumentResponse = entity  # type: ignore[assignment]

    # Step 1: Find pending invite matching current_email
    pending_invite = _find_pending_invite_for_email(document, current_email, role)
    if pending_invite is None:
        return UpdateInviteRecipientResponse(
            entity_id=entity_id,
            entity_type="document",
            status="no_pending_invite",
            new_invite_id=None,
            previous_email=current_email,
            new_email=new_email,
        )

    # Step 2: Delete the existing field invite
    client.delete_field_invite(token, pending_invite.id)

    # Step 3: Replace with new signer via POST /field_invite
    replace_request = ReplaceFieldInviteRequest(
        email=new_email,
        role_id=pending_invite.role_id,
        is_replace=True,
        expiration_days=expiration_days,
        decline_by_signature=decline_by_signature,
        reminder=reminder,
        authentication_type=authentication_type,
        password=password,
        phone=phone,
    )
    replace_response = client.replace_field_invite(token, replace_request)

    # Step 4: Trigger the invite to send to the new signer
    client.trigger_field_invite(token, entity_id)

    return UpdateInviteRecipientResponse(
        entity_id=entity_id,
        entity_type="document",
        status="replaced",
        new_invite_id=replace_response.id,
        previous_email=current_email,
        new_email=new_email,
    )
