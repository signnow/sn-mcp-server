"""
Create from template functions for SignNow MCP server.

This module contains functions for creating documents and document groups
from existing templates and template groups.
"""

from typing import Literal

from signnow_client import DocumentGroupTemplate, SignNowAPIClient

from .models import CreateFromTemplateResponse


def _create_document_from_template(client: SignNowAPIClient, token: str, entity_id: str, name: str | None) -> CreateFromTemplateResponse:
    """Private function to create document from template."""
    from signnow_client import CreateDocumentFromTemplateRequest

    # Prepare request data
    request_data = None
    if name:
        request_data = CreateDocumentFromTemplateRequest(document_name=name)

    # Create document from template
    response = client.create_document_from_template(token, entity_id, request_data)

    # Use provided name or fallback to response document_name or entity_id
    document_name = name or getattr(response, "document_name", None) or f"Document_{response.id[:8]}"

    return CreateFromTemplateResponse(entity_id=response.id, entity_type="document", name=document_name)


def _create_document_group_from_template(client: SignNowAPIClient, token: str, entity_id: str, name: str) -> CreateFromTemplateResponse:
    """Private function to create document group from template group."""
    from signnow_client import CreateDocumentGroupFromTemplateRequest

    if not name:
        raise ValueError("name is required when creating document group from template group")

    # Prepare request data
    request_data = CreateDocumentGroupFromTemplateRequest(group_name=name)

    # Create document group from template group
    response = client.create_document_group_from_template(token, entity_id, request_data)

    # Extract document group ID from response data
    response_data = response.data
    if isinstance(response_data, dict) and "unique_id" in response_data:
        created_id = response_data["unique_id"]
    elif isinstance(response_data, dict) and "id" in response_data:
        created_id = response_data["id"]
    elif isinstance(response_data, dict) and "group_id" in response_data:
        created_id = response_data["group_id"]
    else:
        created_id = str(response_data.get("id", response_data.get("group_id", "unknown")))

    return CreateFromTemplateResponse(entity_id=created_id, entity_type="document_group", name=name)


def _find_template_group(entity_id: str, token: str, client: SignNowAPIClient) -> DocumentGroupTemplate | None:
    """Find template group by ID.

    Args:
        entity_id: ID to search for
        token: Access token for authentication
        client: SignNow API client instance

    Returns:
        DocumentGroupTemplate if found, None otherwise
    """
    template_groups_response = client.get_document_template_groups(token)
    template_groups = template_groups_response.document_group_templates

    # Look for our entity_id in the template groups
    for template_group in template_groups:
        if template_group.template_group_id == entity_id:
            return template_group
    return None


def _create_from_template(entity_id: str, entity_type: Literal["template", "template_group"] | None, name: str | None, token: str, client: SignNowAPIClient) -> CreateFromTemplateResponse:
    """Private function to create a new document or document group from an existing template or template group.

    Args:
        entity_id: ID of the template or template group
        entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
        name: Optional name for the new document group or document (required for template groups)
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        CreateFromTemplateResponse with created entity ID, type and name
    """

    # Find template group if needed (for entity type detection or name extraction)
    found_template_group = None
    if not entity_type:
        found_template_group = _find_template_group(entity_id, token, client)

    # Determine entity type if not provided
    if not entity_type:
        if found_template_group:
            entity_type = "template_group"
        else:
            entity_type = "template"

    if entity_type == "template_group":
        if name is None:
            raise ValueError("name is required when creating document group from template group")
        return _create_document_group_from_template(client, token, entity_id, name)
    else:
        # Create document from template
        return _create_document_from_template(client, token, entity_id, name)
