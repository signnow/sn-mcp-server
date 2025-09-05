"""
SignNow API Data Models - Other Models

Pydantic models for SignNow API responses and requests not related to templates, documents, or document groups.
"""

from typing import Any

from pydantic import BaseModel, Field


class OrganizationSetting(BaseModel):
    """Organization setting from the response."""

    setting: str = Field(..., description="Setting name")
    value: str = Field(..., description="Setting value")


class DocumentDownloadLinkResponse(BaseModel):
    """Response model for document download link."""

    link: str = Field(..., description="Download link for the document")


class FolderSubFolder(BaseModel):
    """Folder subfolder information."""

    id: str = Field(..., description="Subfolder ID")
    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="Subfolder name")
    created: str = Field(..., description="Creation timestamp")
    shared: bool = Field(..., description="Shared status")
    document_count: str = Field(..., description="Document count")
    template_count: int | str | None = Field(None, description="Template count")
    folder_count: str = Field(..., description="Folder count")
    sub_folders: list[dict[str, Any]] | None = Field(None, description="Sub folders")


class Folder(BaseModel):
    """Folder information."""

    id: str = Field(..., description="Folder ID")
    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="Folder name")
    created: str = Field(..., description="Creation timestamp")
    shared: bool = Field(..., description="Shared status")
    document_count: str = Field(..., description="Document count")
    template_count: int | str | None = Field(None, description="Template count")
    folder_count: str = Field(..., description="Folder count")
    sub_folders: list[dict[str, Any]] | None = Field(None, description="Sub folders")
    team_name: str | None = Field(None, description="Team name")
    team_id: str | None = Field(None, description="Team ID")
    team_type: str | None = Field(None, description="Team type")


class GetFoldersResponse(BaseModel):
    """Response model for getting all folders."""

    id: str = Field(..., description="Root folder ID")
    created: str = Field(..., description="Creation timestamp")
    name: str = Field(..., description="Root folder name")
    user_id: str = Field(..., description="User ID")
    parent_id: str | None = Field(None, description="Parent folder ID")
    system_folder: bool = Field(..., description="System folder status")
    shared: bool = Field(..., description="Shared status")
    folders: list[Folder] = Field(..., description="List of folders")
    total_documents: int = Field(..., description="Total documents count")
    documents: list[dict[str, Any]] = Field(..., description="Documents or document groups")


class GetFolderByIdResponse(BaseModel):
    """Response model for getting folder by ID."""

    id: str = Field(..., description="Folder ID")
    created: str = Field(..., description="Creation timestamp")
    name: str = Field(..., description="Folder name")
    user_id: str = Field(..., description="User ID")
    parent_id: str | None = Field(None, description="Parent folder ID")
    system_folder: bool = Field(..., description="System folder status")
    shared: bool = Field(..., description="Shared status")
    folders: list[dict[str, Any]] | None = Field(None, description="Subfolders")
    total_documents: int = Field(..., description="Total documents count")
    documents: list[dict[str, Any]] = Field(..., description="Documents or document groups")


# User API Models


class User(BaseModel):
    """User information from SignNow API."""

    id: str = Field(..., description="User ID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    active: str = Field(..., description="Active status")
    type: int = Field(default=1, description="User type")
    pro: int = Field(..., description="Pro status")
    created: str = Field(..., description="Unix timestamp for when the user was created")
    emails: list[str] = Field(..., description="User emails")
    primary_email: str = Field(..., description="Primary email")
    credits: int = Field(..., description="User credits")
    has_atticus_access: bool = Field(..., description="Has Atticus access")
    cloud_export_account_details: Any | None = Field(None, description="Cloud export account details")
    is_logged_in: bool = Field(..., description="Is logged in status")
    document_count: int = Field(..., description="Document count")
    monthly_document_count: int = Field(..., description="Monthly document count")
    lifetime_document_count: int = Field(..., description="Lifetime document count")
    googleapps: bool = Field(..., description="Google Apps status")
    facebookapps: bool = Field(..., description="Facebook Apps status")
