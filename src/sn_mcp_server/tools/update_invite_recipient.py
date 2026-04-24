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

from .cancel_invite import (
    _resolve_document_group_invite_info,
    _resolve_document_invite_info,
    _resolve_entity_type,
)
from .models import InviteStatusValues, UpdateInviteRecipientResponse

_PENDING_STATUSES = {InviteStatusValues.PENDING, InviteStatusValues.CREATED}


def _find_pending_invites_for_email(
    document: DocumentResponse,
    current_email: str,
    role: str | None,
) -> list[DocumentFieldInviteStatus]:
    """Find all pending/created field invites matching the given email (and optional role).

    Args:
        document: Pre-fetched DocumentResponse with field_invites.
        current_email: Email of the current signer to match.
        role: Optional role name filter for multi-role documents.

    Returns:
        List of matching DocumentFieldInviteStatus entries. Empty list if none found.
    """
    matches: list[DocumentFieldInviteStatus] = []
    for invite in document.field_invites:
        normalized_status = InviteStatusValues.from_raw_status(invite.status)
        if normalized_status not in _PENDING_STATUSES:
            continue
        if invite.email.lower() != current_email.lower():
            continue
        if role is not None and invite.role.lower() != role.lower():
            continue
        matches.append(invite)
    return matches


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
                decline_by_signature=None,
            )
            for action in actions
        ]

        # Build update request
        update_request = UpdateDocGroupInviteStepRequest(
            user_to_update=current_email,
            invite_email=UpdateDocGroupInviteEmail(
                email=new_email,
                reminder=None,
                expiration_days=None,
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


_UNSUPPORTED_INVITE_TYPES = {"freeform", "embedded"}


def _update_document_invite_recipient(
    entity_id: str,
    document: DocumentResponse,
    current_email: str,
    new_email: str,
    role: str | None,
    token: str,
    client: SignNowAPIClient,
) -> UpdateInviteRecipientResponse:
    """Replace the signing recipient on pending field invites for a document.

    For each matching pending invite: Delete → Replace → Trigger (once at the end).

    Args:
        entity_id: Document ID.
        document: Pre-fetched DocumentResponse.
        current_email: Email of the current signer to replace.
        new_email: Email of the new signer.
        role: Optional role name filter.
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        UpdateInviteRecipientResponse with status and new_invite_id.
    """
    pending_invites = _find_pending_invites_for_email(document, current_email, role)
    if not pending_invites:
        return UpdateInviteRecipientResponse(
            entity_id=entity_id,
            entity_type="document",
            status="no_pending_invite",
            new_invite_id=None,
            previous_email=current_email,
            new_email=new_email,
        )

    last_replace_id: str | None = None
    for pending_invite in pending_invites:
        # Delete the existing field invite
        client.delete_field_invite(token, pending_invite.id)

        # Replace with new signer via POST /field_invite
        replace_request = ReplaceFieldInviteRequest(
            email=new_email,
            role_id=pending_invite.role_id,
            is_replace=True,
        )
        replace_response = client.replace_field_invite(token, replace_request)
        last_replace_id = replace_response.id

    # Trigger the invite once after all replacements
    client.trigger_field_invite(token, entity_id)

    return UpdateInviteRecipientResponse(
        entity_id=entity_id,
        entity_type="document",
        status="replaced",
        new_invite_id=last_replace_id,
        previous_email=current_email,
        new_email=new_email,
    )


def _update_invite_recipient(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    current_email: str,
    new_email: str,
    role: str | None,
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

    Args:
        entity_id: Document or document group ID.
        entity_type: Optional entity type discriminator. Auto-detected if None.
        current_email: Email of the current signer to replace.
        new_email: Email of the new signer.
        role: Optional role filter for multi-role documents/steps.
        token: Bearer access token.
        client: SignNow API client.

    Returns:
        UpdateInviteRecipientResponse.
    """
    resolved_type, entity = _resolve_entity_type(client, token, entity_id, entity_type)

    # Check invite type — freeform and embedded invites are not supported
    if resolved_type == "document_group":
        group_data = entity.data  # type: ignore[union-attr]
        invite_type, _status, _ids = _resolve_document_group_invite_info(
            client,
            token,
            entity_id,
            group_data,
        )
    else:
        invite_type, _status, _ids = _resolve_document_invite_info(
            client,
            token,
            entity_id,
            entity,  # type: ignore[arg-type]
        )

    if invite_type in _UNSUPPORTED_INVITE_TYPES:
        return UpdateInviteRecipientResponse(
            entity_id=entity_id,
            entity_type=resolved_type,
            status="unsupported_invite_type",
            new_invite_id=None,
            previous_email=current_email,
            new_email=new_email,
        )

    if resolved_type == "document_group":
        return _update_document_group_invite_recipient(
            entity_id=entity_id,
            document_group=entity,  # type: ignore[arg-type]
            current_email=current_email,
            new_email=new_email,
            role=role,
            token=token,
            client=client,
        )

    return _update_document_invite_recipient(
        entity_id=entity_id,
        document=entity,  # type: ignore[arg-type]
        current_email=current_email,
        new_email=new_email,
        role=role,
        token=token,
        client=client,
    )
