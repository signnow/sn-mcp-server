"""
Create from template functions for SignNow MCP server.

This module contains functions for creating documents and document groups
from existing templates and template groups.
"""

from typing import Literal

from fastmcp import Context
from signnow_client import DocumentGroupTemplate, SignNowAPIClient
from signnow_client.exceptions import SignNowAPIHTTPError

from .models import CreateFromTemplateResponse, EntityCreatedFromTemplate
from .utils import _is_not_found_error


def _create_document_from_template(client: SignNowAPIClient, token: str, entity_id: str, name: str | None) -> CreateFromTemplateResponse:
    """Private function to create document from template."""
    from signnow_client import CreateDocumentFromTemplateRequest

    # Prepare request data
    request_data = None
    if name:
        request_data = CreateDocumentFromTemplateRequest(document_name=name)

    # Create document from template.
    # SignNow returns 400 (not 404) with error code 65582 when the template is not found.
    try:
        response = client.create_document_from_template(token, entity_id, request_data)
    except SignNowAPIHTTPError as exc:
        if _is_not_found_error(exc):
            raise ValueError(f"Template not found: {entity_id}") from None
        raise

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
    try:
        response = client.create_document_group_from_template(token, entity_id, request_data)
    except SignNowAPIHTTPError as exc:
        if _is_not_found_error(exc):
            raise ValueError(f"Template group not found: {entity_id}") from None
        raise

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
        # If name is not provided, try to get it from found_template_group
        if name is None:
            if found_template_group:
                # Use name from found template group
                name = found_template_group.template_group_name
            else:
                # found_template_group was not found, get it by ID to extract name
                found_template_group = _find_template_group(entity_id, token, client)
                if found_template_group:
                    # Use name from found template group
                    name = found_template_group.template_group_name
                else:
                    # Get template group by ID to extract name (more reliable method)
                    try:
                        template_group_data = client.get_document_group_template(token, entity_id)
                        name = template_group_data.group_name
                    except SignNowAPIHTTPError as exc:
                        if _is_not_found_error(exc):
                            raise ValueError(f"Template group not found: {entity_id}") from None
                        raise

        return _create_document_group_from_template(client, token, entity_id, name)
    else:
        # Create document from template
        return _create_document_from_template(client, token, entity_id, name)

async def _resolve_entity(
    entity_id: str,
    entity_type: Literal["document", "document_group", "template", "template_group"],
    name: str | None,
    token: str,
    client: SignNowAPIClient,
    ctx: Context | None = None,
) -> EntityCreatedFromTemplate:
    """Detect entity type and materialise templates before API dispatch.

    When entity_type is 'template' or 'template_group', creates a new entity from the
    template and reports progress steps 1/3 and 2/3 via ctx. When entity_type is
    'document' or 'document_group', returns immediately with no API calls.

    Args:
        entity_id: ID of the document, document group, template, or template group
        entity_type: Explicit type (not auto-detected here — caller must resolve first)
        name: Optional name for the newly created entity (required for template_group)
        token: Access token for SignNow API
        client: SignNow API client instance
        ctx: FastMCP context for progress reporting (steps 1/3 and 2/3)

    Returns:
        EntityCreatedFromTemplate with dispatch-ready entity_id/type and optional
        created_entity_* fields populated when a template was materialised
    """
    if entity_type in ("template", "template_group"):
        if ctx:
            await ctx.report_progress(progress=1, total=3)
        created = _create_from_template(entity_id, entity_type, name, token, client)
        if ctx:
            await ctx.report_progress(progress=2, total=3)
        return EntityCreatedFromTemplate(
            entity_id=created.entity_id,
            entity_type=created.entity_type,
            created_entity_id=created.entity_id,
            created_entity_type=created.entity_type,
            created_entity_name=created.name,
        )

    return EntityCreatedFromTemplate(entity_id=entity_id, entity_type=entity_type)

