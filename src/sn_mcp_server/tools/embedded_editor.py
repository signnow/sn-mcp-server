"""
Embedded editor functions for SignNow MCP server.

This module contains functions for creating embedded editor for documents and document groups
from the SignNow API.
"""

from typing import Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient

from .create_from_template import _create_from_template
from .models import (
    CreateEmbeddedEditorResponse,
)
from .utils import _detect_entity_type


def _create_document_group_embedded_editor(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration_minutes: int | None
) -> CreateEmbeddedEditorResponse:
    """Private function to create document group embedded editor."""
    from signnow_client import (
        CreateDocumentGroupEmbeddedEditorRequest as SignNowEmbeddedEditorRequest,
    )

    request_data = SignNowEmbeddedEditorRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration_minutes)

    response = client.create_document_group_embedded_editor(token, entity_id, request_data)

    return CreateEmbeddedEditorResponse(editor_entity="document_group", editor_url=response.data.url)


def _create_document_embedded_editor(
    client: SignNowAPIClient, token: str, entity_id: str, redirect_uri: str | None, redirect_target: str | None, link_expiration_minutes: int | None
) -> CreateEmbeddedEditorResponse:
    """Private function to create document embedded editor."""
    from signnow_client import CreateDocumentEmbeddedEditorRequest

    request_data = CreateDocumentEmbeddedEditorRequest(redirect_uri=redirect_uri, redirect_target=redirect_target, link_expiration=link_expiration_minutes)

    response = client.create_document_embedded_editor(token, entity_id, request_data)

    return CreateEmbeddedEditorResponse(editor_entity="document", editor_url=response.data.url)


async def _create_embedded_editor(
    entity_id: str,
    entity_type: Literal["document", "document_group", "template", "template_group"] | None,
    redirect_uri: str | None,
    redirect_target: str | None,
    link_expiration_minutes: int | None,
    token: str,
    client: SignNowAPIClient,
    name: str | None = None,
    ctx: Context | None = None,
) -> CreateEmbeddedEditorResponse:
    """Create embedded editor for a document, document group, template, or template group.

    When entity_type is 'template' or 'template_group', creates a document/group
    from the template first, then creates the embedded editor on the created entity.

    Args:
        entity_id: ID of the document, document group, template, or template group
        entity_type: Entity type (optional, auto-detected if None)
        redirect_uri: Optional redirect URI for the editor link
        redirect_target: Optional redirect target for the editor link
        link_expiration_minutes: Link lifetime in minutes (15–43200). None uses API default (15 min).
        token: Access token for SignNow API
        client: SignNow API client instance
        name: Optional name for the new entity (used only for template/template_group)
        ctx: FastMCP context for progress reporting (used for template flows)

    Returns:
        CreateEmbeddedEditorResponse with editor details and optional created entity info
    """
    created_entity_id: str | None = None
    created_entity_type: str | None = None
    created_entity_name: str | None = None

    if entity_type is None:
        entity_type = _detect_entity_type(entity_id, token, client)

    if entity_type in ("template", "template_group"):
        if ctx:
            await ctx.report_progress(progress=1, total=3)
        created = _create_from_template(entity_id, entity_type, name, token, client)
        created_entity_id = created.entity_id
        created_entity_type = created.entity_type
        created_entity_name = created.name
        entity_id = created.entity_id
        entity_type = created.entity_type  # now "document" or "document_group"
        if ctx:
            await ctx.report_progress(progress=2, total=3)

    if entity_type == "document_group":
        editor_response = _create_document_group_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration_minutes)
    else:
        editor_response = _create_document_embedded_editor(client, token, entity_id, redirect_uri, redirect_target, link_expiration_minutes)

    if ctx and created_entity_id :
        await ctx.report_progress(progress=3, total=3)

    return CreateEmbeddedEditorResponse(
        editor_entity=editor_response.editor_entity,
        editor_url=editor_response.editor_url,
        created_entity_id=created_entity_id,
        created_entity_type=created_entity_type,
        created_entity_name=created_entity_name,
    )
