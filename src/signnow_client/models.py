"""
SignNow API Data Models

Pydantic models for SignNow API responses and requests.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr, HttpUrl


class Thumbnail(BaseModel):
    """URLs to document thumbnails in different sizes."""
    small: HttpUrl = Field(..., description="≈ 120 px thumbnail")
    medium: HttpUrl = Field(..., description="≈ 640 px thumbnail")
    large: HttpUrl = Field(..., description="≈ 1920 px thumbnail")


class Template(BaseModel):
    """Compact information about a template inside a group."""
    id: str = Field(..., description="Template ID (40-character HEX)")
    name: str = Field(..., description="Template name")
    thumbnail: Thumbnail
    roles: List[str] = Field(..., description="Roles defined for this template")


class DocumentGroupTemplate(BaseModel):
    """Single item of the `document_group_templates` array."""
    folder_id: Optional[str] = Field(
        None, description="Folder ID, if the group is stored in a folder"
    )
    last_updated: int = Field(
        ..., description="Unix timestamp of the last update"
    )
    template_group_id: str = Field(..., description="Document-group template ID")
    template_group_name: str = Field(..., description="Name of the template group")
    owner_email: EmailStr = Field(..., description="Owner of the template group")
    templates: List[Template]
    is_prepared: bool = Field(..., description="Whether the group is ready for sending")
    own_as_merged: bool = Field(..., description="Send documents as a merged file")


class DocumentGroupTemplatesResponse(BaseModel):
    """Full JSON response from `/user/documentgroup/templates`."""
    document_group_templates: List[DocumentGroupTemplate]
    document_group_template_total_count: int = Field(
        ..., description="Total number of template groups in the response"
    )


class DocumentGroupDocument(BaseModel):
    """Document information within a document group."""
    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    thumbnail: Thumbnail
    has_credit_card_number: bool = Field(..., description="Whether document contains credit card numbers")
    roles: List[str] = Field(..., description="Roles defined for this document")


class DocumentGroup(BaseModel):
    """Single document group from the `/user/documentgroups` endpoint."""
    last_updated: int = Field(..., description="Unix timestamp of the last update")
    group_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    invite_id: Optional[str] = Field(None, description="Invite ID for this group")
    invite_status: Optional[str] = Field(None, description="Status of the invite (e.g., 'pending')")
    documents: List[DocumentGroupDocument] = Field(..., description="List of documents in this group")


class OrganizationSetting(BaseModel):
    """Organization setting from the response."""
    setting: str = Field(..., description="Setting name")
    value: str = Field(..., description="Setting value")


class DocumentGroupsResponse(BaseModel):
    """Full JSON response from `/user/documentgroups`."""
    document_groups: List[DocumentGroup]
    document_group_total_count: int = Field(..., description="Total number of document groups")
    originator_organization_settings: List[OrganizationSetting] = Field(
        ..., description="Organization settings for the originator"
    )


 