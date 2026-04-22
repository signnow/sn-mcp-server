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
from signnow_client.models.document_groups import (
    GetDocumentGroupV2Response,
    UpdateDocGroupInviteActionAttributes,
    UpdateDocGroupInviteEmail,
    UpdateDocGroupInviteStepRequest,
)
from signnow_client.models.templates_and_documents import (
    DocumentFieldInviteStatus,
    DocumentResponse,
    FieldInviteActionStatus,
    FieldInviteStatus,
    FieldInviteStepStatus,
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


def _find_pending_steps_for_email(
    invite: FieldInviteStatus,
    current_email: str,
    role: str | None,
) -> list[tuple[FieldInviteStepStatus, list[FieldInviteActionStatus]]]:
    """Find pending invite steps matching the given email in a document group field invite.

    Args:
        invite: FieldInviteStatus from GetFieldInviteResponse.invite (contains steps[].actions[]).
        current_email: Email of the current signer to match.
        role: Optional role name filter.

    Returns:
        List of (step, matching_actions) tuples. Empty list if nothing matches.
    """
    result = []
    for step in invite.steps:
        normalized_status = InviteStatusValues.from_raw_status(step.status)
        if normalized_status not in _PENDING_STATUSES:
            continue

        matching_actions = []
        for action in step.actions:
            if action.email is None:
                continue
            if action.email.lower() != current_email.lower():
                continue
            if role is not None and action.role_name.lower() != role.lower():
                continue
            matching_actions.append(action)

        if matching_actions:
            result.append((step, matching_actions))

    return result


def _update_document_group_invite_recipient(
    entity_id: str,
    document_group: GetDocumentGroupV2Response,
    current_email: str,
    new_email: str,
    role: str | None,
    expiration_days: int | None,
    reminder: int | None,
    decline_by_signature: int | None,
    token: str,
    client: SignNowAPIClient,
) -> UpdateInviteRecipientResponse:
    """Replace the signing recipient on a pending field invite for a document group.

    Args:
        entity_id: Document group ID.
        document_group: Pre-fetched GetDocumentGroupV2Response.
        current_email: Email of the current signer to replace.
        new_email: Email of the new signer.
        role: Optional role name filter.
        expiration_days: Optional days until invite expires.
        reminder: Optional reminder days.
        decline_by_signature: Optional decline button setting (0 or 1).
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        UpdateInviteRecipientResponse with status and updated_steps.
    """
    invite_id = document_group.data.invite_id
    if invite_id is None:
        return UpdateInviteRecipientResponse(
            entity_id=entity_id,
            entity_type="document_group",
            status="no_pending_invite",
            new_invite_id=None,
            previous_email=current_email,
            new_email=new_email,
        )

    # Fetch full invite details
    invite_response = client.get_field_invite(token, entity_id, invite_id)
    matching_steps = _find_pending_steps_for_email(invite_response.invite, current_email, role)

    if not matching_steps:
        return UpdateInviteRecipientResponse(
            entity_id=entity_id,
            entity_type="document_group",
            status="no_pending_invite",
            new_invite_id=None,
            previous_email=current_email,
            new_email=new_email,
        )

    updated_step_ids = []
    for step, actions in matching_steps:
        # Build per-document action attributes from matching actions
        update_invite_action_attributes = [
            UpdateDocGroupInviteActionAttributes(
                document_id=action.document_id,
                allow_reassign=None,
                decline_by_signature=str(decline_by_signature) if decline_by_signature is not None else None,
            )
            for action in actions
        ]

        # Build update request
        update_request = UpdateDocGroupInviteStepRequest(
            user_to_update=current_email,
            invite_email=UpdateDocGroupInviteEmail(
                email=new_email,
                reminder=reminder,
                expiration_days=expiration_days,
            ),
            update_invite_action_attributes=update_invite_action_attributes,
            replace_with_this_user=new_email,
        )

        # Update the step
        client.update_document_group_invite_step(token, entity_id, invite_id, step.id, update_request)
        updated_step_ids.append(step.id)

    return UpdateInviteRecipientResponse(
        entity_id=entity_id,
        entity_type="document_group",
        status="replaced",
        new_invite_id=invite_id,
        previous_email=current_email,
        new_email=new_email,
        updated_steps=updated_step_ids,
    )


def _update_invite_recipient(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    current_email: str,
    new_email: str,
    role: str | None,  # exlclude
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

    Documents: Three-step SignNow replace-signer flow:
        1. Resolve entity type and fetch document data
        2. Find pending invite matching current_email
        3. Delete → Replace → Trigger

    Document Groups: Update invite step flow:
        1. Resolve entity type and fetch document group data
        2. Find pending steps matching current_email
        3. Update each step via /invitestep/{step_id}/update

    Note: For document groups, authentication_type, password, and phone parameters
    are not used — the update endpoint uses a different mechanism.

    Args:
        entity_id: Document or document group ID.
        entity_type: Optional entity type discriminator. Auto-detected if None.
        current_email: Email of the current signer to replace.
        new_email: Email of the new signer.
        role: Optional role filter for multi-role documents/steps.
        expiration_days: Optional days until invite expires (max 30).
        decline_by_signature: Optional decline button setting (0 or 1).
        reminder: Optional reminder days (max 30).
        authentication_type: Optional identity verification type (documents only).
        password: Optional password for identity verification (documents only).
        phone: Optional phone number for identity verification (documents only).
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        UpdateInviteRecipientResponse.

    Raises:
        ValueError: When no pending invite is found for current_email.
    """
    resolved_type, entity = _resolve_entity_type(client, token, entity_id, entity_type)

    if resolved_type == "document_group":
        return _update_document_group_invite_recipient(
            entity_id=entity_id,
            document_group=entity,  # type: ignore[arg-type]
            current_email=current_email,
            new_email=new_email,
            role=role,
            expiration_days=expiration_days,
            reminder=reminder,
            decline_by_signature=decline_by_signature,
            token=token,
            client=client,
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
