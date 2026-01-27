"""
Signing link functions for SignNow MCP server.

This module contains functions for generating signing links for documents and document groups
from the SignNow web app.
"""

from typing import Literal
from urllib.parse import urlencode

from signnow_client import SignNowAPIClient

from .document import _get_document
from .models import SigningLinkResponse


def _get_signing_link(entity_id: str, entity_type: Literal["document", "document_group"] | None, token: str, client: SignNowAPIClient) -> SigningLinkResponse:
    """Private function to generate signing link for a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        SigningLinkResponse with signing link
    """

    document_group = _get_document(client, token, entity_id, entity_type)

    if document_group.entity_type not in ("document", "document_group"):
        raise ValueError(f"Entity with ID {entity_id} is not a document or document group")

    if not document_group.invite:
        raise ValueError(f"To sign, an invite must exist for {document_group.entity_type} with ID {document_group.entity_id}")

    app_base = str(client.cfg.app_base).rstrip("/")
    resolved_entity_id = document_group.entity_id

    if document_group.entity_type == "document_group":
        query = urlencode({"document_group_id": resolved_entity_id, "access_token": token})
        link = f"{app_base}/webapp/documentgroup/signing?{query}&unwrap"
    else:
        link = f"{app_base}/webapp/document/{resolved_entity_id}?access_token={token}"

    return SigningLinkResponse(link=link)
