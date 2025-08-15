"""
MCP Tools Data Models

Pydantic models for MCP tools results and responses.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TemplateSummary(BaseModel):
    """Simplified template information for listing."""
    id: str = Field(..., description="Template group ID")
    name: str = Field(..., description="Template group name")
    folder_id: Optional[str] = Field(None, description="Folder ID if stored in folder")
    last_updated: int = Field(..., description="Unix timestamp of last update")
    is_prepared: bool = Field(..., description="Whether the group is ready for sending")
    roles: List[str] = Field(..., description="All unique roles from all templates in the group")


class TemplateSummaryList(BaseModel):
    """List of simplified template summaries."""
    templates: List[TemplateSummary]
    total_count: int = Field(..., description="Total number of templates")


class SimplifiedDocumentGroupDocument(BaseModel):
    """Simplified document information for MCP tools."""
    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    roles: List[str] = Field(..., description="Roles defined for this document")


class SimplifiedDocumentGroup(BaseModel):
    """Simplified document group for MCP tools."""
    last_updated: int = Field(..., description="Unix timestamp of the last update")
    group_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    invite_id: Optional[str] = Field(None, description="Invite ID for this group")
    invite_status: Optional[str] = Field(None, description="Status of the invite (e.g., 'pending')")
    documents: List[SimplifiedDocumentGroupDocument] = Field(..., description="List of documents in this group")


class SimplifiedDocumentGroupsResponse(BaseModel):
    """Simplified response for MCP tools with document groups"""
    document_groups: List[SimplifiedDocumentGroup]
    document_group_total_count: int = Field(..., description="Total number of document groups") 