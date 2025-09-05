"""
Document listing functions for SignNow MCP server.

This module contains functions for retrieving documents and document groups
from the SignNow API and converting them to simplified formats for MCP tools.
"""

from typing import Any

from signnow_client import SignNowAPIClient

from .models import (
    SimplifiedDocumentGroup,
    SimplifiedDocumentGroupDocument,
    SimplifiedDocumentGroupsResponse,
)


def _list_document_groups(token: str, signnow_config: Any, limit: int = 50, offset: int = 0) -> SimplifiedDocumentGroupsResponse:
    """Provide simplified list of document groups with basic fields.

    Args:
        token: Access token for SignNow API
        signnow_config: SignNow configuration object
        limit: Maximum number of document groups to return (default: 50, max: 50)
        offset: Number of document groups to skip for pagination (default: 0)

    Returns:
        SimplifiedDocumentGroupsResponse with document groups
    """
    # Use the client to get document groups - API already applies limit and offset
    client = SignNowAPIClient(signnow_config)
    full_response = client.get_document_groups(token, limit=limit, offset=offset)

    # Convert to simplified models for MCP tools
    simplified_groups = []
    for group in full_response.document_groups:
        simplified_docs = []
        for doc in group.documents:
            simplified_doc = SimplifiedDocumentGroupDocument(id=doc.id, name=doc.document_name, roles=doc.roles)
            simplified_docs.append(simplified_doc)

        simplified_group = SimplifiedDocumentGroup(
            last_updated=group.last_updated,
            group_id=group.group_id,
            group_name=group.group_name,
            invite_id=group.invite_id,
            invite_status=group.invite_status,
            documents=simplified_docs,
        )
        simplified_groups.append(simplified_group)

    # Use the total count from API response, not the length of current page
    return SimplifiedDocumentGroupsResponse(document_groups=simplified_groups, document_group_total_count=full_response.document_group_total_count)
