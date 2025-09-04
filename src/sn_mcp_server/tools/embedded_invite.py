"""
Embedded invite functions for SignNow MCP server.

This module contains functions for creating embedded invites for documents and document groups
from the SignNow API.
"""

from typing import Any, Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .models import (
    CreateEmbeddedInviteFromTemplateResponse,
    CreateEmbeddedInviteResponse,
    EmbeddedInviteOrder,
)


def _create_document_group_embedded_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[Any], document_group: Any) -> CreateEmbeddedInviteResponse:
    """Private function to create document group embedded invite."""
    from signnow_client import (
        CreateEmbeddedInviteRequest as SignNowEmbeddedInviteRequest,
    )
    from signnow_client import EmbeddedInviteSigner, EmbeddedInviteStep

    # Convert orders to embedded invite steps
    invite_steps = []
    for order_info in orders:
        signers = []
        for recipient in order_info.recipients:
            # Create EmbeddedInviteSigner for each recipient
            signer_data = {
                "email": recipient.email,
                "auth_method": recipient.auth_method,
                "first_name": recipient.first_name,
                "last_name": recipient.last_name,
                "language": "en",  # Default language
                "required_preset_signature_name": None,
                "redirect_uri": recipient.redirect_uri,
                "decline_redirect_uri": recipient.decline_redirect_uri,
                "close_redirect_uri": recipient.close_redirect_uri,
                "delivery_type": recipient.delivery_type,
                "subject": recipient.subject,
                "message": recipient.message,
                "documents": [{"id": doc.id, "role": recipient.role_name, "action": recipient.action} for doc in document_group.documents if recipient.role_name in doc.roles],
            }

            # Only add redirect_target if redirect_uri is provided and not empty
            if recipient.redirect_uri and recipient.redirect_uri.strip():
                signer_data["redirect_target"] = recipient.redirect_target

            signer = EmbeddedInviteSigner(**signer_data)
            signers.append(signer)

        step = EmbeddedInviteStep(order=order_info.order, signers=signers)
        invite_steps.append(step)

    request_data = SignNowEmbeddedInviteRequest(invites=invite_steps, sign_as_merged=True)  # Send as merged document group

    response = client.create_embedded_invite(token, entity_id, request_data)

    # Generate links for recipients with delivery_type='link'
    recipient_links = []
    for order_info in orders:
        for recipient in order_info.recipients:
            if recipient.delivery_type == "link":
                from signnow_client import GenerateEmbeddedInviteLinkRequest

                link_request = GenerateEmbeddedInviteLinkRequest(email=recipient.email, auth_method=recipient.auth_method)
                link_response = client.generate_embedded_invite_link(token, entity_id, response.data.id, link_request)
                recipient_links.append({"role": recipient.role_name, "link": link_response.data.link})

    return CreateEmbeddedInviteResponse(invite_id=response.data.id, invite_entity="document_group", recipient_links=recipient_links)


def _create_document_embedded_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[Any]) -> CreateEmbeddedInviteResponse:
    """Private function to create document embedded invite."""
    from signnow_client import (
        CreateDocumentEmbeddedInviteRequest,
        DocumentEmbeddedInvite,
    )

    # Convert orders to document embedded invite
    invites = []
    for order_info in orders:
        signers = []
        for recipient in order_info.recipients:
            # Create DocumentEmbeddedInvite for each recipient
            invite_data = {
                "email": recipient.email,
                "auth_method": recipient.auth_method,
                "first_name": recipient.first_name,
                "last_name": recipient.last_name,
                "language": "en",  # Default language
                "required_preset_signature_name": None,
                "redirect_uri": recipient.redirect_uri,
                "decline_redirect_uri": recipient.decline_redirect_uri,
                "close_redirect_uri": recipient.close_redirect_uri,
                "delivery_type": recipient.delivery_type,
                "subject": recipient.subject,
                "message": recipient.message,
                "documents": [{"id": entity_id, "role": recipient.role_name, "action": recipient.action}],
            }

            # Only add redirect_target if redirect_uri is provided and not empty
            if recipient.redirect_uri and recipient.redirect_uri.strip():
                invite_data["redirect_target"] = recipient.redirect_target

            doc_invite = DocumentEmbeddedInvite(**invite_data)
            signers.append(doc_invite)

        invites.append({"order": str(order_info.order), "signers": signers})

    request_data = CreateDocumentEmbeddedInviteRequest(invites=invites)

    response = client.create_document_embedded_invite(token, entity_id, request_data)

    # Generate links for recipients with delivery_type='link'
    recipient_links = []
    for order_info in orders:
        for recipient in order_info.recipients:
            if recipient.delivery_type == "link":
                from signnow_client import GenerateDocumentEmbeddedInviteLinkRequest

                link_request = GenerateDocumentEmbeddedInviteLinkRequest(email=recipient.email, auth_method=recipient.auth_method)
                link_response = client.generate_document_embedded_invite_link(token, entity_id, response.data.id, link_request)
                recipient_links.append({"role": recipient.role_name, "link": link_response.data.link})

    return CreateEmbeddedInviteResponse(invite_id=response.data.id, invite_entity="document", recipient_links=recipient_links)


def _create_embedded_invite(
    entity_id: str, entity_type: Literal["document", "document_group"] | None, orders: list[EmbeddedInviteOrder], token: str, client: SignNowAPIClient
) -> CreateEmbeddedInviteResponse:
    """Private function to create embedded invite for signing a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        orders: List of orders with recipients
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        CreateEmbeddedInviteResponse with invite ID and entity type
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

    # Validate orders
    if not orders:
        raise ValueError("At least one order with recipients is required")

    if entity_type == "document_group":
        # Create document group embedded invite
        # Get the document group if we don't have it yet
        if not document_group:
            document_group = client.get_document_group(token, entity_id)

        return _create_document_group_embedded_invite(client, token, entity_id, orders, document_group)
    else:
        # Create document embedded invite
        return _create_document_embedded_invite(client, token, entity_id, orders)


async def _create_embedded_invite_from_template(
    entity_id: str,
    entity_type: Literal["template", "template_group"] | None,
    name: str | None,
    orders: list[EmbeddedInviteOrder],
    token: str,
    client: SignNowAPIClient,
    ctx: Context,
) -> CreateEmbeddedInviteFromTemplateResponse:
    """Private function to create document/group from template and create embedded invite immediately.

    Args:
        entity_id: ID of the template or template group
        entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        name: Optional name for the new document or document group
        orders: List of orders with recipients for the embedded invite
        token: Access token for SignNow API
        client: SignNow API client instance
        ctx: FastMCP context for progress reporting

    Returns:
        CreateEmbeddedInviteFromTemplateResponse with created entity info and embedded invite details
    """
    # Report initial progress
    await ctx.report_progress(progress=1, total=3)

    # Import and use the create from template function directly
    from .create_from_template import _create_from_template

    # Use the imported function to create from template
    created_entity = _create_from_template(entity_id, entity_type, name, token, client)

    # Report progress after template creation
    await ctx.report_progress(progress=2, total=3)

    if created_entity.entity_type == "document_group":
        # Create document group embedded invite
        document_group = client.get_document_group(token, created_entity.entity_id)
        invite_response = _create_document_group_embedded_invite(client, token, created_entity.entity_id, orders, document_group)
        # Report final progress after embedded invite creation
        await ctx.report_progress(progress=3, total=3)
        return CreateEmbeddedInviteFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            invite_id=invite_response.invite_id,
            invite_entity=invite_response.invite_entity,
            recipient_links=invite_response.recipient_links,
        )
    else:
        # Create document embedded invite
        invite_response = _create_document_embedded_invite(client, token, created_entity.entity_id, orders)
        # Report final progress after embedded invite creation
        await ctx.report_progress(progress=3, total=3)
        return CreateEmbeddedInviteFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            invite_id=invite_response.invite_id,
            invite_entity=invite_response.invite_entity,
            recipient_links=invite_response.recipient_links,
        )
