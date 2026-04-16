"""
Embedded invite functions for SignNow MCP server.

This module contains functions for creating embedded invites for documents and document groups
from the SignNow API.
"""

from typing import Any, Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .create_from_template import _resolve_entity
from .models import (
    CreateEmbeddedInviteResponse,
    EmbeddedInviteOrder,
    EmbeddedInviteRecipient,
)
from .utils import _detect_entity_type


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
                "documents": [{"id": doc.id, "role": recipient.role, "action": recipient.action} for doc in document_group.documents if recipient.role in doc.roles],
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
                recipient_links.append({"role": recipient.role, "link": link_response.data.link})

    return CreateEmbeddedInviteResponse(document_group_invite_id=response.data.id, invite_entity="document_group", recipient_links=recipient_links)


def _create_document_embedded_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[EmbeddedInviteOrder]) -> CreateEmbeddedInviteResponse:
    """Private function to create document embedded invite."""
    from signnow_client import (
        CreateDocumentEmbeddedInviteRequest,
        DocumentEmbeddedInvite,
        GenerateDocumentEmbeddedInviteLinkRequest,
    )

    flat_recipients: list[tuple[int, EmbeddedInviteRecipient]] = [
        (order_info.order, recipient)
        for order_info in orders
        for recipient in order_info.recipients
    ]

    invites = []
    for order, recipient in flat_recipients:
        invite = recipient.model_dump()
        invite["order"] = order
        invite["language"] = "en"  # Default language
        invite["required_preset_signature_name"] = None
        invites.append(DocumentEmbeddedInvite(**invite))
    
    request_data = CreateDocumentEmbeddedInviteRequest(invites=invites)
    response = client.create_document_embedded_invite(token, entity_id, request_data)

    invite_by_email_order = {(i.email, i.order): i for i in response.data}

    recipient_links = []
    for order, recipient in flat_recipients:
        # link generation only succeeds for invites in 'pending' status, with multiple signing orders, only order-1 invites are pending immediately
        if recipient.delivery_type == "link" and order == 1: 
            invite = invite_by_email_order.get((recipient.email, order))
            if invite is None:
                msg = f"No invite returned for email '{recipient.email}' on document '{entity_id}'"
                raise ValueError(msg)
            link_request = GenerateDocumentEmbeddedInviteLinkRequest(auth_method=recipient.auth_method)
            link_response = client.generate_document_embedded_invite_link(token, entity_id, invite.id, link_request)
            recipient_links.append({"role": recipient.role, "link": link_response.data["link"], "document_invite_id": invite.id})

    return CreateEmbeddedInviteResponse(document_group_invite_id=None, invite_entity="document", recipient_links=recipient_links)


async def _create_embedded_invite(
    entity_id: str,
    entity_type: Literal["document", "document_group", "template", "template_group"] | None,
    orders: list[EmbeddedInviteOrder],
    token: str,
    client: SignNowAPIClient,
    name: str | None = None,
    ctx: Context | None = None,
) -> CreateEmbeddedInviteResponse:
    """Create embedded invite for signing a document, document group, template, or template group.

    When entity_type is 'template' or 'template_group', creates a document/group
    from the template first, then creates the embedded invite on the created entity.

    Args:
        entity_id: ID of the document, document group, template, or template group
        entity_type: Entity type (optional, auto-detected if None)
        orders: List of orders with recipients
        token: Access token for SignNow API
        client: SignNow API client instance
        name: Optional name for the new entity (used only for template/template_group)
        ctx: FastMCP context for progress reporting (used for template flows)

    Returns:
        CreateEmbeddedInviteResponse with invite details and optional created entity info
    """
    if entity_type is None:
        entity_type = _detect_entity_type(entity_id, token, client)

    created = await _resolve_entity(entity_id, entity_type, name, token, client, ctx)
    entity_id = created.entity_id
    entity_type = created.entity_type

    if entity_type == "document_group":
        document_group = client.get_document_group(token, entity_id)
        invite_response = _create_document_group_embedded_invite(client, token, entity_id, orders, document_group)
    else:
        invite_response = _create_document_embedded_invite(client, token, entity_id, orders)

    if ctx and created.created_entity_id:
        await ctx.report_progress(progress=3, total=3)

    return CreateEmbeddedInviteResponse(
        document_group_invite_id=invite_response.document_group_invite_id,
        invite_entity=invite_response.invite_entity,
        recipient_links=invite_response.recipient_links,
        created_entity_id=created.created_entity_id,
        created_entity_type=created.created_entity_type,
        created_entity_name=created.created_entity_name,
    )
