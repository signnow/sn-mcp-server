"""
SignNow API Data Models - Other Models

Pydantic models for SignNow API responses and requests not related to templates, documents, or document groups.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .folders_lite import _parse_int_value
from .templates_and_documents import DocumentThumbnail


class DocumentRoleName(BaseModel):
    """Document role name."""

    name: str | None = Field(None, description="Role name")


class DocumentFieldInvite(BaseModel):
    """Field invite inside a document item."""

    id: str = Field(..., description="Field invite ID")
    signer_user_id: str | None = Field(None, description="Signer user ID")
    status: str | None = Field(None, description="Invite status")
    created: int | None = Field(None, description="Unix timestamp when invite was created")
    email: str | None = Field(None, description="Signer email")
    role: str | None = Field(None, description="Signer role")
    updated: int | None = Field(None, description="Unix timestamp when invite was updated")
    expiration_time: int | None = Field(None, description="Unix timestamp when invite expires")
    role_id: str | None = Field(None, description="Role ID")

    @field_validator("created", "updated", "expiration_time", mode="before")
    @classmethod
    def _normalize_int_fields(cls, value: Any) -> int | None:
        return _parse_int_value(value)


class OrganizationSetting(BaseModel):
    """Organization setting from the response."""

    setting: str = Field(..., description="Setting name")
    value: str = Field(..., description="Setting value")


class DocumentDownloadLinkResponse(BaseModel):
    """Response model for document download link."""

    link: str = Field(..., description="Download link for the document")


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
