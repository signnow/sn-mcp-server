"""
Embedded editor functions for SignNow MCP server.

This module contains functions for creating embedded editor for documents and document groups
from the SignNow API.
"""

from typing import Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .models import (
    CreateEmbeddedEditorFromTemplateResponse,
    CreateEmbeddedEditorResponse,
)


def _create_document_group_embedded_editor(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration: int | None
) -> CreateEmbeddedEditorResponse:
    """Private function to create document group embedded editor."""
    from signnow_client import (
        CreateDocumentGroupEmbeddedEditorRequest as SignNowEmbeddedEditorRequest,
    )

    request_data = SignNowEmbeddedEditorRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration)

    response = client.create_document_group_embedded_editor(token, entity_id, request_data)

    return CreateEmbeddedEditorResponse(editor_entity="document_group", editor_url=response.data.url)


def _create_document_embedded_editor(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration: int | None
) -> CreateEmbeddedEditorResponse:
    """Private function to create document embedded editor."""
    from signnow_client import CreateDocumentEmbeddedEditorRequest

    request_data = CreateDocumentEmbeddedEditorRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration)

    response = client.create_document_embedded_editor(token, entity_id, request_data)

    return CreateEmbeddedEditorResponse(editor_entity="document", editor_url=response.data.url)


def _create_embedded_editor(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    redirect_uri: str | None,
    redirect_target: str | None,
    link_expiration: int | None,
    token: str,
    client: SignNowAPIClient,
) -> CreateEmbeddedEditorResponse:
    """Private function to create embedded editor for editing a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        redirect_uri: Optional redirect URI for the editor link
        redirect_target: Optional redirect target for the editor link
        link_expiration: Optional number of minutes for the editor link to expire (15-43200)
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        CreateEmbeddedEditorResponse with editor ID and entity type
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
        # Create document group embedded editor
        # Get the document group if we don't have it yet
        if not document_group:
            document_group = client.get_document_group(token, entity_id)

        return _create_document_group_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration)
    else:
        # Create document embedded editor
        return _create_document_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration)


async def _create_embedded_editor_from_template(
    entity_id: str,
    entity_type: Literal["template", "template_group"] | None,
    name: str | None,
    redirect_uri: str | None,
    redirect_target: str | None,
    link_expiration: int | None,
    token: str,
    client: SignNowAPIClient,
    ctx: Context,
) -> CreateEmbeddedEditorFromTemplateResponse:
    """Private function to create document/group from template and create embedded editor immediately.

    Args:
        entity_id: ID of the template or template group
        entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        name: Optional name for the new document or document group
        redirect_uri: Optional redirect URI after completion
        redirect_target: Optional redirect target: 'self', 'blank', or 'self' (default)
        link_expiration: Optional link expiration in minutes (15-43200)
        token: Access token for SignNow API
        client: SignNow API client instance
        ctx: FastMCP context for progress reporting

    Returns:
        CreateEmbeddedEditorFromTemplateResponse with created entity info and embedded editor details
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
        editor_response = _create_document_group_embedded_editor(client, token, created_entity.entity_id, redirect_uri, redirect_target, link_expiration)
        # Report final progress after embedded editor creation
        await ctx.report_progress(progress=3, total=3)
        return CreateEmbeddedEditorFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            editor_id=editor_response.editor_url,
            editor_entity=editor_response.editor_entity,
            editor_url=editor_response.editor_url,
        )
    else:
        editor_response = _create_document_embedded_editor(client, token, created_entity.entity_id, redirect_uri, redirect_target, link_expiration)
        # Report final progress after embedded editor creation
        await ctx.report_progress(progress=3, total=3)
        return CreateEmbeddedEditorFromTemplateResponse(
            created_entity_id=created_entity.entity_id,
            created_entity_type=created_entity.entity_type,
            created_entity_name=created_entity.name,
            editor_id=editor_response.editor_url,
            editor_entity=editor_response.editor_entity,
            editor_url=editor_response.editor_url,
        )
