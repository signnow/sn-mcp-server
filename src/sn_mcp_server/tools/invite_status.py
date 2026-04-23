"""
Invite status functions for SignNow MCP server.

This module contains functions for getting invite status for documents and document groups
from the SignNow API.
"""

from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.models import DocumentResponse, ListDocumentFreeformInvitesResponse
from signnow_client.models.document_groups import GetDocumentGroupV2Response

from .models import DocumentGroupStatusAction, DocumentGroupStatusStep, InviteStatus, InviteStatusValues


def _get_document_group_status(client: SignNowAPIClient, token: str, document_group_data: GetDocumentGroupV2Response, document_group_id: str) -> InviteStatus:
    """
    Get document group status information.

    This function extracts invite_id from document group data, then gets field invite details
    and returns formatted status information.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_group_data: Document group data
        document_group_id: ID of the document group

    Returns:
        InviteStatus with invite_id, status, and steps information

    Raises:
        ValueError: If group not found or no invite_id found
    """
    group_response = document_group_data
    invite_id = group_response.data.invite_id

    if not invite_id:
        raise ValueError(f"No invite_id found for document group {document_group_id}")

    # Get field invite details
    invite_response = client.get_field_invite(token, document_group_id, invite_id)
    invite = invite_response.invite

    # Transform steps and actions to our format
    steps = []
    for step in invite.steps:
        actions = []
        for action in step.actions:
            # Only include actions with email (skip email_group actions)
            if action.email:
                actions.append(DocumentGroupStatusAction(action=action.action, email=action.email, document_id=action.document_id, status=action.status, role=action.role_name))

        steps.append(DocumentGroupStatusStep(status=step.status, order=step.order, actions=actions))

    return InviteStatus(invite_id=invite.id, status=invite.status, steps=steps, invite_mode="field")


def _get_document_status(client: SignNowAPIClient, token: str, document_data: DocumentResponse) -> InviteStatus:
    """
    Get document status information.

    This function extracts field_invites from document data, then transforms them
    into InviteStatus format.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_data: Document data

    Returns:
        InviteStatus with document field invites information

    Raises:
        ValueError: If document not found or no field invites found
    """
    document_response = document_data
    field_invites = document_response.field_invites

    if not field_invites:
        raise ValueError(f"No field invites found for document {document_response.id}")

    # Transform field_invites to InviteStatus format
    # For documents, we create a single step with all field invites as actions
    actions = []
    for field_invite in field_invites:
        # Only include field invites with email (skip email_group invites)
        if field_invite.email:
            actions.append(
                DocumentGroupStatusAction(
                    action="sign",  # Documents typically have sign action
                    email=field_invite.email,
                    document_id=document_response.id,
                    status=field_invite.status,
                    role=field_invite.role,
                )
            )

    # Create a single step with all actions
    steps = []
    if actions:
        steps.append(DocumentGroupStatusStep(status=field_invites[0].status, order=1, actions=actions))  # Use first invite status as step status

    # Use first field invite ID as invite_id, or generate a placeholder
    invite_id = field_invites[0].id if field_invites else f"doc_{document_response.id}"

    return InviteStatus(
        invite_id=invite_id,
        status=field_invites[0].status if field_invites else InviteStatusValues.UNKNOWN,
        steps=steps,
        invite_mode="field",
    )


def _map_document_freeform_to_invite_status(document_id: str, freeform_response: ListDocumentFreeformInvitesResponse) -> InviteStatus:
    """Build InviteStatus from GET /v2/documents/{id}/free-form-invites response."""
    items = freeform_response.data
    if not items:
        raise ValueError(f"No field or freeform invite found for document {document_id}")

    actions: list[DocumentGroupStatusAction] = []
    first_invite_id = ""
    first_status = ""
    for item in items:
        if not (item.email and item.email.strip()):
            continue
        if not first_invite_id:
            first_invite_id = item.id
            first_status = item.status
        actions.append(
            DocumentGroupStatusAction(
                action="sign",
                email=item.email.strip(),
                document_id=document_id,
                status=item.status,
                role=None,
            )
        )
    if not actions:
        raise ValueError(f"No freeform invite signers with an email for document {document_id}")
    steps = [DocumentGroupStatusStep(status=first_status, order=1, actions=actions)]
    return InviteStatus(invite_id=first_invite_id, status=first_status, steps=steps, invite_mode="freeform")


def _get_document_group_freeform_status(client: SignNowAPIClient, token: str, document_group_id: str, freeform_invite_id: str) -> InviteStatus:
    """Build InviteStatus from GET /v2/document-groups/{id}/documents (signature_requests)."""
    doc_list = client.list_document_group_documents(token, document_group_id)
    actions: list[DocumentGroupStatusAction] = []
    first_status = ""
    for doc in doc_list.data:
        for req in doc.signature_requests:
            if not (req.email and req.email.strip()):
                continue
            if not first_status:
                first_status = req.status
            actions.append(
                DocumentGroupStatusAction(
                    action="sign",
                    email=req.email.strip(),
                    document_id=doc.id,
                    status=req.status,
                    role=None,
                )
            )
    if not actions:
        raise ValueError(f"No signers with an email in signature_requests for freeform document group {document_group_id!r} (freeform_invite_id={freeform_invite_id!r})")
    steps = [DocumentGroupStatusStep(status=first_status, order=1, actions=actions)]
    return InviteStatus(
        invite_id=freeform_invite_id,
        status=first_status,
        steps=steps,
        invite_mode="freeform",
    )


def _document_group_invite_dispatch(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    group: GetDocumentGroupV2Response,
) -> InviteStatus:
    """Field invite first, then freeform (group documents list)."""
    data = group.data
    if data.invite_id:
        return _get_document_group_status(client, token, group, entity_id)
    freeform = data.freeform_invite
    if freeform and freeform.id:
        return _get_document_group_freeform_status(client, token, entity_id, freeform.id)
    raise ValueError(f"No field or freeform invite found for document group {entity_id}")


def _document_invite_dispatch(client: SignNowAPIClient, token: str, document: DocumentResponse) -> InviteStatus:
    """Field invites first, then document freeform list."""
    if document.field_invites:
        return _get_document_status(client, token, document)
    freeform = client.list_document_freeform_invites(token, document.id)
    if not freeform.data:
        raise ValueError(f"No field or freeform invite found for document {document.id}")
    return _map_document_freeform_to_invite_status(document.id, freeform)


def _get_invite_status(entity_id: str, entity_type: Literal["document", "document_group"] | None, token: str, client: SignNowAPIClient) -> InviteStatus:
    """Private function to get invite status for a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        InviteStatus with invite ID, status, and steps information
    """
    # Auto-detect entity type when not provided by probing document_group → document.
    # The first probe's failure is the expected negative signal ("not a document group")
    # that triggers the fallback; the second arm raises when both probes fail.
    if not entity_type:
        try:
            document_group = client.get_document_group_v2(token, entity_id)
            return _document_group_invite_dispatch(client, token, entity_id, document_group)
        except Exception:  # noqa: S110
            pass
        try:
            document = client.get_document(token, entity_id)
            return _document_invite_dispatch(client, token, document)
        except Exception:
            raise ValueError(f"Entity with ID {entity_id} not found as either document group or document") from None

    # Entity type is provided — dispatch directly to the appropriate fetcher.
    if entity_type == "document_group":
        return _document_group_invite_dispatch(client, token, entity_id, client.get_document_group_v2(token, entity_id))
    return _document_invite_dispatch(client, token, client.get_document(token, entity_id))
