"""
Embedded sending functions for SignNow MCP server.

This module contains functions for creating embedded sending for documents and document groups
from the SignNow API.
"""

from typing import Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .models import (
    CreateEmbeddedSendingFromTemplateResponse,
    CreateEmbeddedSendingResponse,
)


def _create_document_group_embedded_sending(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration: int | None, sending_type: str | None
) -> CreateEmbeddedSendingResponse:
    """Private function to create document group embedded sending."""
    from signnow_client import (
        CreateDocumentGroupEmbeddedSendingRequest as SignNowEmbeddedSendingRequest,
    )

    request_data = SignNowEmbeddedSendingRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration, type=sending_type)

    response = client.create_document_group_embedded_sending(token, entity_id, request_data)

    return CreateEmbeddedSendingResponse(sending_entity="document_group", sending_url=response.data.url)


def _create_document_embedded_sending(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration: int | None, sending_type: str | None
) -> CreateEmbeddedSendingResponse:
    """Private function to create document embedded sending."""
    from signnow_client import CreateDocumentEmbeddedSendingRequest

    # Map sending type to entity type for documents BEFORE making the request
    if sending_type == "send-invite":
        mapped_type = "invite"
    else:  # manage or edit
        mapped_type = "document"

    request_data = CreateDocumentEmbeddedSendingRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration, type=mapped_type)

    response = client.create_document_embedded_sending(token, entity_id, request_data)

    return CreateEmbeddedSendingResponse(sending_entity="document", sending_url=response.data.url)


def _create_embedded_sending(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    redirect_uri: str | None,
    redirect_target: str | None,
    link_expiration: int | None,
    sending_type: str | None,
    token: str,
    client: SignNowAPIClient,
) -> CreateEmbeddedSendingResponse:
    """Private function to create embedded sending for managing, editing, or sending invites for a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        redirect_uri: Optional redirect URI for the sending link
        redirect_target: Optional redirect target for the sending link
        link_expiration: Optional number of days for the sending link to expire (14-45)
        sending_type: Specifies the sending step: 'manage' (default), 'edit', 'send-invite'
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        CreateEmbeddedSendingResponse with entity type and URL
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
        # Create document group embedded sending
        # Get the document group if we don't have it yet
        if not document_group:
            document_group = client.get_document_group(token, entity_id)

        return _create_document_group_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration, sending_type)
    else:
        # Create document embedded sending
        return _create_document_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration, sending_type)


async def _create_embedded_sending_from_template(
    entity_id: str,
    entity_type: Literal["template", "template_group"] | None,
    name: str | None,
    redirect_uri: str | None,
    redirect_target: str | None,
    link_expiration: int | None,
    sending_type: str | None,
    token: str,
    client: SignNowAPIClient,
    ctx: Context,
) -> CreateEmbeddedSendingFromTemplateResponse:
    """Private function to create document/group from template and create embedded sending immediately.

    Args:
        entity_id: ID of the template or template group
        entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        name: Optional name for the new document or document group
        redirect_uri: Optional redirect URI after completion
        redirect_target: Optional redirect target: 'self', 'blank', or 'self' (default)
        link_expiration: Optional link expiration in days (14-45)
        sending_type: Type of sending step: 'manage', 'edit', or 'send-invite'
        token: Access token for SignNow API
        client: SignNow API client instance
        ctx: FastMCP context for progress reporting

    Returns:
        CreateEmbeddedSendingFromTemplateResponse with created entity info and embedded sending details
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
        sending_response = _create_document_group_embedded_sending(client, token, created_entity.entity_id, redirect_uri, redirect_target, link_expiration, sending_type)
        # Report final progress after embedded sending creation
        await ctx.report_progress(progress=3, total=3)
        return CreateEmbeddedSendingFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            sending_id=sending_response.sending_url,
            sending_entity=sending_response.sending_entity,
            sending_url=sending_response.sending_url,
        )
    else:
        # Create document embedded sending
        sending_response = _create_document_embedded_sending(client, token, created_entity.entity_id, redirect_uri, redirect_target, link_expiration, sending_type)
        # Report final progress after embedded sending creation
        await ctx.report_progress(progress=3, total=3)
        return CreateEmbeddedSendingFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            sending_id=sending_response.sending_url,
            sending_entity=sending_response.sending_entity,
            sending_url=sending_response.sending_url,
        )
