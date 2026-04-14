"""
Document view functions for SignNow MCP server.

This module generates embedded view links for documents and document groups.
The links open a read-only viewer that requires no SignNow login.
"""

from __future__ import annotations

import pathlib
from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models import (
    CreateDocumentEmbeddedViewRequest,
    CreateDocumentGroupEmbeddedViewRequest,
)

from .models import ViewDocumentResponse

VIEWER_RESOURCE_URI: str = "ui://signnow/document-viewer"

_STATIC_DIR = pathlib.Path(__file__).parent / "static"
_VIEWER_HTML: str = (_STATIC_DIR / "document_viewer.html").read_text(encoding="utf-8")


def _view_document(
    entity_id: str,
    entity_type: Literal["document", "document_group"] | None,
    link_expiration_minutes: int | None,
    token: str,
    client: SignNowAPIClient,
) -> ViewDocumentResponse:
    """Generate an embedded view link for a document or document group.

    Auto-detects entity type if not provided (tries document_group first per AGENTS.md,
    then document as fallback).

    Args:
        entity_id: ID of the document or document group
        entity_type: Explicit entity type (optional, saves one API call if provided).
            Accepted values: 'document' or 'document_group'.
        link_expiration_minutes: Link lifetime in minutes (43200–518400). None = API default (43200 = 30 days).
        token: Access token for authentication
        client: SignNow API client instance

    Returns:
        ViewDocumentResponse with view_link, document_name, entity_id, entity_type

    Raises:
        ValueError: If entity_type is None and the entity is not found as either
            document group or document.
        SignNowAPIError: If the entity is not found when entity_type is explicit,
            or if the embedded-view API returns 403/422.
    """
    document_name: str | None = None

    if entity_type is None:
        # Auto-detect: document_group first (per AGENTS.md), document as fallback.
        # Only SignNowAPINotFoundError (404) triggers fallback — auth/rate-limit/
        # server errors propagate so the caller sees the real failure.
        try:
            group = client.get_document_group_v2(token, entity_id)
            entity_type = "document_group"
            document_name = group.data.name
        except SignNowAPINotFoundError:
            try:
                doc = client.get_document(token, entity_id)
                entity_type = "document"
                document_name = doc.document_name
            except SignNowAPINotFoundError:
                raise ValueError(f"Entity with ID '{entity_id}' not found as either document group or document") from None

    # Fetch entity name when explicit entity_type was provided (name not yet resolved)
    if document_name is None:
        if entity_type == "document_group":
            group = client.get_document_group_v2(token, entity_id)
            document_name = group.data.name
        else:
            doc = client.get_document(token, entity_id)
            document_name = doc.document_name

    # Generate the embedded view link
    if entity_type == "document_group":
        request = CreateDocumentGroupEmbeddedViewRequest(link_expiration=link_expiration_minutes)
        response = client.create_document_group_embedded_view(token, entity_id, request)
        view_link = response.data.link
    else:
        request_doc = CreateDocumentEmbeddedViewRequest(link_expiration=link_expiration_minutes)
        response_doc = client.create_document_embedded_view(token, entity_id, request_doc)
        view_link = response_doc.data.link

    return ViewDocumentResponse(
        view_link=view_link,
        document_name=document_name,
        entity_id=entity_id,
        entity_type=entity_type,
    )
