import json
import time
from fastmcp import Context
from typing import Dict, List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from fastmcp.server.dependencies import get_http_headers
from ..token_provider import TokenProvider
from signnow_client import (
    Thumbnail,
    Template,
    DocumentGroupTemplate,
    DocumentGroupTemplatesResponse
)
from .models import (
    TemplateSummary,
    TemplateSummaryList,
    SimplifiedDocumentGroupDocument,
    SimplifiedDocumentGroup,
    SimplifiedDocumentGroupsResponse
)


def bind(mcp, cfg):
    # Initialize token provider
    token_provider = TokenProvider()

    @mcp.tool(
        name="list_templates",
        description="Get simplified list of templates with basic information"
    )
    def list_templates(ctx: Context) -> TemplateSummaryList:
        """Provide simplified list of templates with basic fields."""
        from signnow_client import SignNowAPIClient
        
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        try:
            # Use the client to get document template groups - now returns validated model
            client = SignNowAPIClient(token_provider.signnow_config)
            full_response = client.get_document_template_groups(token, limit=50)
            
            # Преобразуем в упрощенную структуру
            templates = []
            for template_group in full_response.document_group_templates:
                # Собираем все уникальные роли из всех шаблонов в группе
                all_roles = set()
                for template in template_group.templates:
                    all_roles.update(template.roles)
                
                template_summary = TemplateSummary(
                    id=template_group.template_group_id,
                    name=template_group.template_group_name,
                    folder_id=template_group.folder_id,
                    last_updated=template_group.last_updated,
                    is_prepared=template_group.is_prepared,
                    roles=list(all_roles)
                )
                templates.append(template_summary)
            
            return TemplateSummaryList(
                templates=templates,
                total_count=full_response.document_group_template_total_count
            )
        except ValueError as e:
            raise ValueError(f"Error getting templates: {str(e)}")

    @mcp.tool(
        name="list_document_groups",
        description="Get simplified list of document groups with basic information"
    )
    def list_document_groups(ctx: Context, limit: int = 50, offset: int = 0) -> SimplifiedDocumentGroupsResponse:
        """Provide simplified list of document groups with basic fields.
        
        Args:
            limit: Maximum number of document groups to return (default: 50)
            offset: Number of document groups to skip for pagination (default: 0)
        """
        from signnow_client import SignNowAPIClient
        
        headers = get_http_headers()
        token = token_provider.get_access_token(headers)
        
        if not token:
            raise ValueError("No access token available")

        try:
            # Use the client to get document groups - API already applies limit and offset
            client = SignNowAPIClient(token_provider.signnow_config)
            full_response = client.get_document_groups(token, limit=limit, offset=offset)
            
            # Convert to simplified models for MCP tools
            simplified_groups = []
            for group in full_response.document_groups:
                simplified_docs = []
                for doc in group.documents:
                    simplified_doc = SimplifiedDocumentGroupDocument(
                        id=doc.id,
                        name=doc.name,
                        roles=doc.roles
                    )
                    simplified_docs.append(simplified_doc)
                
                simplified_group = SimplifiedDocumentGroup(
                    last_updated=group.last_updated,
                    group_id=group.group_id,
                    group_name=group.group_name,
                    invite_id=group.invite_id,
                    invite_status=group.invite_status,
                    documents=simplified_docs
                )
                simplified_groups.append(simplified_group)
            
            # Use the total count from API response, not the length of current page
            return SimplifiedDocumentGroupsResponse(
                document_groups=simplified_groups,
                document_group_total_count=full_response.document_group_total_count
            )
        except ValueError as e:
            raise ValueError(f"Error getting document groups: {str(e)}")
