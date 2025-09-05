"""
Invite status functions for SignNow MCP server.

This module contains functions for getting invite status for documents and document groups
from the SignNow API.
"""

from typing import Any, Literal

from signnow_client import SignNowAPIClient

from .models import DocumentGroupStatusAction, DocumentGroupStatusStep, InviteStatus


def _get_document_group_status(client: SignNowAPIClient, token: str, document_group_data: Any, document_group_id: str) -> InviteStatus:
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
                actions.append(DocumentGroupStatusAction(action=action.action, email=action.email, document_id=action.document_id, status=action.status, role_name=action.role_name))

        steps.append(DocumentGroupStatusStep(status=step.status, order=step.order, actions=actions))

    return InviteStatus(invite_id=invite.id, status=invite.status, steps=steps)


def _get_document_status(client: SignNowAPIClient, token: str, document_data: Any) -> InviteStatus:
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
                    role_name=field_invite.role,
                )
            )

    # Create a single step with all actions
    steps = []
    if actions:
        steps.append(DocumentGroupStatusStep(status=field_invites[0].status, order=1, actions=actions))  # Use first invite status as step status

    # Use first field invite ID as invite_id, or generate a placeholder
    invite_id = field_invites[0].id if field_invites else f"doc_{document_response.id}"

    return InviteStatus(invite_id=invite_id, status=field_invites[0].status if field_invites else "unknown", steps=steps)


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
    # Determine entity type if not provided and get entity data
    document_group = None
    document = None

    if not entity_type:
        # Try to determine entity type by attempting to get document group first (higher priority)
        try:
            document_group = client.get_document_group_v2(token, entity_id)
            entity_type = "document_group"
        except Exception:
            # If document group not found, try document
            try:
                document = client.get_document(token, entity_id)
                entity_type = "document"
            except Exception:
                raise ValueError(f"Entity with ID {entity_id} not found as either document group or document") from None
    else:
        # Entity type is provided, get the entity data
        if entity_type == "document_group":
            document_group = client.get_document_group_v2(token, entity_id)
        else:
            document = client.get_document(token, entity_id)

    if entity_type == "document_group":
        # Get document group status using the already fetched data
        return _get_document_group_status(client, token, document_group, entity_id)
    else:
        # Get document status using the already fetched data
        return _get_document_status(client, token, document)
