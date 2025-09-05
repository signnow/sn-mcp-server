"""
Send invite functions for SignNow MCP server.

This module contains functions for sending invites to sign documents and document groups
from the SignNow API.
"""

from typing import Any, Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .models import InviteOrder, SendInviteFromTemplateResponse, SendInviteResponse


def _send_document_group_field_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[Any], document_group: Any) -> SendInviteResponse:
    """Private function to send document group field invite."""
    from signnow_client import (
        CreateFieldInviteRequest,
        FieldInviteAction,
        FieldInviteEmail,
        FieldInviteStep,
    )

    # Convert orders to field invite steps
    invite_steps = []
    for order_info in orders:
        actions = []
        invite_emails = []

        for recipient in order_info.recipients:
            # Create FieldInviteEmail for each recipient
            invite_email = FieldInviteEmail(email=recipient.email, subject=recipient.subject, message=recipient.message)
            invite_emails.append(invite_email)

            # Create FieldInviteAction only for documents with matching roles
            for document in document_group.documents:
                # Only create action if the document has the required role
                if recipient.role_name in document.roles:
                    # Only include redirect_target if redirect_uri is provided
                    action_data = {
                        "email": recipient.email,
                        "role_name": recipient.role_name,
                        "action": recipient.action,
                        "document_id": document.id,  # Use actual document ID from the group
                        "redirect_uri": recipient.redirect_uri,
                        "decline_redirect_uri": recipient.decline_redirect_uri,
                        "close_redirect_uri": recipient.close_redirect_uri,
                    }

                    # Only add redirect_target if redirect_uri is provided and not empty
                    if recipient.redirect_uri and recipient.redirect_uri.strip():
                        action_data["redirect_target"] = recipient.redirect_target

                    action = FieldInviteAction(**action_data)
                    actions.append(action)

        step = FieldInviteStep(order=order_info.order, invite_emails=invite_emails, invite_actions=actions)  # All recipients' emails with their subjects and messages
        invite_steps.append(step)

    request_data = CreateFieldInviteRequest(invite_steps=invite_steps, cc=[], cc_subject=None, cc_message=None)  # TODO: Add CC support if needed

    response = client.create_field_invite(token, entity_id, request_data)

    return SendInviteResponse(invite_id=response.id, invite_entity="document_group")


def _send_document_field_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[Any]) -> SendInviteResponse:
    """Private function to send document field invite."""
    from signnow_client import (
        CreateDocumentFieldInviteRequest,
        DocumentFieldInviteRecipient,
    )

    # Get user info to use primary email as 'from' address
    user_info = client.get_user_info(token)
    from_email = user_info.primary_email

    # Convert orders to document field invite recipients
    recipients = []
    for order_info in orders:
        for recipient in order_info.recipients:
            # Create DocumentFieldInviteRecipient for each recipient
            recipient_data = {
                "email": recipient.email,
                "role": recipient.role_name,
                "order": order_info.order,
                "redirect_uri": recipient.redirect_uri,
                "decline_by_signature": "1" if recipient.decline_redirect_uri else "0",
                "subject": recipient.subject,
                "message": recipient.message,
            }

            # Only add redirect_target if redirect_uri is provided and not empty
            if recipient.redirect_uri and recipient.redirect_uri.strip():
                recipient_data["redirect_target"] = recipient.redirect_target

            doc_recipient = DocumentFieldInviteRecipient(**recipient_data)
            recipients.append(doc_recipient)

    # Create document field invite request
    request_data = CreateDocumentFieldInviteRequest(document_id=entity_id, to=recipients, from_=from_email)

    response = client.create_document_field_invite(token, entity_id, request_data)

    return SendInviteResponse(invite_id=response.status, invite_entity="document")  # Document field invite returns status, not id


def _send_invite(entity_id: str, entity_type: Literal["document", "document_group"] | None, orders: list[InviteOrder], token: str, client: SignNowAPIClient) -> SendInviteResponse:
    """Private function to send invite to sign a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        orders: List of orders with recipients
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        SendInviteResponse with invite ID and entity type
    """

    # Determine entity type if not provided
    document_group = None  # Store document group if found during auto-detection

    if not entity_type:
        # Try to determine entity type by attempting to get document group first (higher priority)
        try:
            document_group = client.get_document_group(token, entity_id)
            entity_type = "document_group"
        except Exception:
            # If document group not found, try document
            try:
                client.get_document(token, entity_id)
                entity_type = "document"
            except Exception:
                raise ValueError(f"Entity with ID {entity_id} not found as either document group or document") from None

    if entity_type == "document_group":
        # Send document group field invite
        # Get the document group if we don't have it yet
        if not document_group:
            document_group = client.get_document_group(token, entity_id)

        return _send_document_group_field_invite(client, token, entity_id, orders, document_group)
    else:
        # Send document field invite
        return _send_document_field_invite(client, token, entity_id, orders)


async def _send_invite_from_template(
    entity_id: str, entity_type: Literal["template", "template_group"] | None, name: str | None, orders: list[InviteOrder], token: str, client: SignNowAPIClient, ctx: Context
) -> SendInviteFromTemplateResponse:
    """Private function to create document/group from template and send invite immediately.

    Args:
        entity_id: ID of the template or template group
        entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        name: Optional name for the new document or document group
        orders: List of orders with recipients for the invite
        token: Access token for SignNow API
        client: SignNow API client instance
        ctx: FastMCP context for progress reporting

    Returns:
        SendInviteFromTemplateResponse with created entity info and invite details
    """
    # Report initial progress
    await ctx.report_progress(progress=1, total=3)

    # Import and use the create from template function directly
    from .create_from_template import _create_from_template

    # Use the imported function to create from template
    created_entity = _create_from_template(entity_id, entity_type, name, token, client)

    # Report progress after template creation
    await ctx.report_progress(progress=2, total=3)

    # Then send invite
    invite_response = _send_invite(created_entity.entity_id, created_entity.entity_type or "document", orders, token, client)

    # Report final progress after invite sending
    await ctx.report_progress(progress=3, total=3)

    return SendInviteFromTemplateResponse(
        created_entity_id=created_entity.entity_id,
        created_entity_type=created_entity.entity_type,
        created_entity_name=created_entity.name,
        invite_id=invite_response.invite_id,
        invite_entity=invite_response.invite_entity,
    )
