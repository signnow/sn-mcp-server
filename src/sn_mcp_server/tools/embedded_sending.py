"""
Embedded sending functions for SignNow MCP server.

This module contains functions for creating embedded sending for documents and document groups
from the SignNow API.
"""

from typing import Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .create_from_template import _resolve_entity
from .models import (
    CreateEmbeddedSendingResponse,
)
from .utils import _detect_entity_type


def _create_document_group_embedded_sending(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration_minutes: int | None, sending_type: str | None
) -> CreateEmbeddedSendingResponse:
    """Private function to create document group embedded sending.

    Args:
        link_expiration_minutes: Link lifetime in minutes (15–45).
    """
    from signnow_client import (
        CreateDocumentGroupEmbeddedSendingRequest as SignNowEmbeddedSendingRequest,
    )

    request_data = SignNowEmbeddedSendingRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration_minutes, type=sending_type)

    response = client.create_document_group_embedded_sending(token, entity_id, request_data)

    return CreateEmbeddedSendingResponse(sending_entity="document_group", sending_url=response.data.url)


def _create_document_embedded_sending(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration_minutes: int | None, sending_type: str | None
) -> CreateEmbeddedSendingResponse:
    """Private function to create document embedded sending.

    Args:
        link_expiration_minutes: Link lifetime in minutes (15–45).
    """
    from signnow_client import CreateDocumentEmbeddedSendingRequest

    # Map sending type to entity type for documents BEFORE making the request
    if sending_type == "send-invite":
        mapped_type = "invite"
    else:  # manage or edit
        mapped_type = "document"

    request_data = CreateDocumentEmbeddedSendingRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration_minutes, type=mapped_type)

    response = client.create_document_embedded_sending(token, entity_id, request_data)

    return CreateEmbeddedSendingResponse(sending_entity="document", sending_url=response.data.url)


async def _create_embedded_sending(
    entity_id: str,
    entity_type: Literal["document", "document_group", "template", "template_group"] | None,
    redirect_uri: str | None,
    redirect_target: str | None,
    link_expiration_minutes: int | None,
    sending_type: str | None,
    token: str,
    client: SignNowAPIClient,
    name: str | None = None,
    ctx: Context | None = None,
) -> CreateEmbeddedSendingResponse:
    """Create embedded sending for a document, document group, template, or template group.

    When entity_type is 'template' or 'template_group', creates a document/group
    from the template first, then creates the embedded sending on the created entity.

    Args:
        entity_id: ID of the document, document group, template, or template group
        entity_type: Entity type (optional, auto-detected if None)
        redirect_uri: Optional redirect URI for the sending link
        redirect_target: Optional redirect target for the sending link
        link_expiration_minutes: Link lifetime in minutes (15–45). None uses API default (15 min).
        sending_type: Specifies the sending step: 'manage' (default), 'edit', 'send-invite'
        token: Access token for SignNow API
        client: SignNow API client instance
        name: Optional name for the new entity (used only for template/template_group)
        ctx: FastMCP context for progress reporting (used for template flows)

    Returns:
        CreateEmbeddedSendingResponse with sending details and optional created entity info
    """
    if entity_type is None:
        entity_type = _detect_entity_type(entity_id, token, client)

    created = await _resolve_entity(entity_id, entity_type, name, token, client, ctx)
    entity_id = created.entity_id
    entity_type = created.entity_type

    if entity_type == "document_group":
        sending_response = _create_document_group_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration_minutes, sending_type)
    else:
        sending_response = _create_document_embedded_sending(client, token, entity_id, redirect_uri, redirect_target, link_expiration_minutes, sending_type)

    if ctx and created.created_entity_id:
        await ctx.report_progress(progress=3, total=3)

    return CreateEmbeddedSendingResponse(
        sending_entity=sending_response.sending_entity,
        sending_url=sending_response.sending_url,
        created_entity_id=created.created_entity_id,
        created_entity_type=created.created_entity_type,
        created_entity_name=created.created_entity_name,
    )
