"""
Document download link functions for SignNow MCP server.

This module contains functions for getting download links for documents and document groups
from the SignNow API.
"""

from typing import Literal

from signnow_client import MergeDocumentsRequest, SignNowAPIClient

from .models import DocumentDownloadLinkResponse


def _get_document_download_link(entity_id: str, entity_type: Literal["document", "document_group"] | None, token: str, client: SignNowAPIClient) -> DocumentDownloadLinkResponse:
    """Private function to get download link for a document or document group.

    Args:
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        DocumentDownloadLinkResponse with download link
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
        # For document group, we need to merge all documents first
        # Get the document group if we don't have it yet
        if not document_group:
            document_group = client.get_document_group(token, entity_id)

        # Extract document IDs from the group
        document_ids = [doc.id for doc in document_group.documents]

        if not document_ids:
            raise ValueError(f"Document group {entity_id} contains no documents")

        # If only one document, just get its download link directly
        if len(document_ids) == 1:
            response = client.get_document_download_link(token, document_ids[0])
            return DocumentDownloadLinkResponse(link=response.link)

        # Merge all documents in the group
        merge_request = MergeDocumentsRequest(name=document_group.group_name, document_ids=document_ids, upload_document=True)

        merge_response = client.merge_documents(token, merge_request)

        # Get download link for the merged document
        response = client.get_document_download_link(token, merge_response.document_id)
        return DocumentDownloadLinkResponse(link=response.link)
    else:
        # For single document, just get its download link
        response = client.get_document_download_link(token, entity_id)
        return DocumentDownloadLinkResponse(link=response.link)
