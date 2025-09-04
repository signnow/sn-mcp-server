"""
MCP Tools Data Models

Pydantic models for MCP tools results and responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class TemplateSummary(BaseModel):
    """Simplified template information for listing."""

    id: str = Field(..., description="Template group ID")
    name: str = Field(..., description="Template group name")
    entity_type: str = Field(..., description="Type of entity: 'template' or 'template_group'")
    folder_id: str | None = Field(None, description="Folder ID if stored in folder")
    last_updated: int = Field(..., description="Unix timestamp of last update")
    is_prepared: bool = Field(..., description="Whether the group is ready for sending")
    roles: list[str] = Field(..., description="All unique roles from all templates in the group")


class TemplateSummaryList(BaseModel):
    """List of simplified template summaries."""

    templates: list[TemplateSummary]
    total_count: int = Field(..., description="Total number of templates")


class DocumentField(BaseModel):
    """Document field information."""

    id: str = Field(..., description="Field ID")
    type: str = Field(..., description="Field type")
    role_id: str = Field(..., description="Role ID associated with this field")
    value: str = Field(..., description="Field value")
    name: str = Field(..., description="Field name")


class DocumentGroupDocument(BaseModel):
    """Document information for MCP tools."""

    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    roles: list[str] = Field(..., description="Roles defined for this document")
    fields: list[DocumentField] = Field(default=[], description="Fields defined in this document")


class DocumentGroup(BaseModel):
    """Document group model with all fields."""

    last_updated: int = Field(..., description="Unix timestamp of the last update")
    entity_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    entity_type: str = Field(..., description="Type of entity: 'document' or 'document_group'")
    invite_id: str | None = Field(None, description="Invite ID for this group")
    invite_status: str | None = Field(None, description="Status of the invite (e.g., 'pending')")
    documents: list[DocumentGroupDocument] = Field(..., description="List of documents in this group")


class SimplifiedDocumentGroupDocument(BaseModel):
    """Simplified document information for MCP tools."""

    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    roles: list[str] = Field(..., description="Roles defined for this document")


class SimplifiedDocumentGroup(BaseModel):
    """Simplified document group for MCP tools."""

    last_updated: int = Field(..., description="Unix timestamp of the last update")
    group_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    invite_id: str | None = Field(None, description="Invite ID for this group")
    invite_status: str | None = Field(None, description="Status of the invite (e.g., 'pending')")
    documents: list[SimplifiedDocumentGroupDocument] = Field(..., description="List of documents in this group")


class SimplifiedDocumentGroupsResponse(BaseModel):
    """Simplified response for MCP tools with document groups"""

    document_groups: list[SimplifiedDocumentGroup]
    document_group_total_count: int = Field(..., description="Total number of document groups")


# Invite sending models
class InviteRecipient(BaseModel):
    """Recipient information for invite."""

    email: str = Field(..., description="Recipient's email address")
    role_name: str = Field(..., description="Recipient's role name in the document")
    message: str | None = Field(None, description="Custom email message for the recipient")
    subject: str | None = Field(None, description="Custom email subject for the recipient")
    action: str = Field(..., description="Allowed action with a document. Possible values: 'view', 'sign', 'approve'")
    redirect_uri: str | None = Field(None, description="Link that opens after completion")
    redirect_target: str | None = Field("blank", description="Redirect target: 'blank' for new tab, 'self' for same tab")
    decline_redirect_uri: str | None = Field(None, description="URL that opens after decline")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Close' button")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class InviteOrder(BaseModel):
    """Order information for invite."""

    order: int = Field(..., description="Order number for this step")
    recipients: list[InviteRecipient] = Field(..., description="List of recipients for this order")


class SendInviteResponse(BaseModel):
    """Response model for sending invite."""

    invite_id: str = Field(..., description="ID of the created invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")


# Embedded invite models
class EmbeddedInviteRecipient(BaseModel):
    """Recipient information for embedded invite."""

    email: str = Field(..., description="Recipient's email address")
    role_name: str = Field(..., description="Recipient's role name in the document")
    action: str = Field(..., description="Allowed action with a document. Possible values: 'view', 'sign', 'approve'")
    auth_method: str = Field("none", description="Authentication method in integrated app: 'password', 'email', 'mfa', 'biometric', 'social', 'other', 'none'")
    first_name: str | None = Field(None, description="Recipient's first name")
    last_name: str | None = Field(None, description="Recipient's last name")
    redirect_uri: str | None = Field(None, description="Link that opens after completion")
    decline_redirect_uri: str | None = Field(None, description="URL that opens after decline")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Close' button")
    redirect_target: str | None = Field("self", description="Redirect target: 'blank' for new tab, 'self' for same tab")
    subject: str | None = Field(None, description="Invite email subject (max 1000 chars)")
    message: str | None = Field(None, description="Invite email message (max 5000 chars)")
    delivery_type: str | None = Field("link", description="Invite delivery method: 'email' or 'link', use 'link' if you wand to get a link to sign. If you want to send an email, use 'email'")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class EmbeddedInviteOrder(BaseModel):
    """Order information for embedded invite."""

    order: int = Field(..., description="Order number for this step")
    recipients: list[EmbeddedInviteRecipient] = Field(..., description="List of recipients for this order")


class CreateEmbeddedInviteRequest(BaseModel):
    """Request model for creating embedded invite."""

    entity_id: str = Field(..., description="ID of the document or document group")
    entity_type: str | None = Field(None, description="Type of entity: 'document' or 'document_group'")
    orders: list[EmbeddedInviteOrder] = Field(..., description="List of orders with recipients")


class CreateEmbeddedInviteResponse(BaseModel):
    """Response model for creating embedded invite."""

    invite_id: str = Field(..., description="ID of the created embedded invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")
    recipient_links: list[dict[str, str]] = Field(..., description="Array of objects with role and link for recipients with delivery_type='link'")


class CreateEmbeddedEditorRequest(BaseModel):
    """Request model for creating embedded editor."""

    entity_id: str = Field(..., description="ID of the document or document group")
    entity_type: str | None = Field(None, description="Type of entity: 'document' or 'document_group'. If not provided, will be auto-detected")
    redirect_uri: str | None = Field(None, description="URL to redirect to after editing is complete")
    redirect_target: str | None = Field("self", description="Redirect target: 'self' for same tab, 'blank' for new tab")
    link_expiration: int | None = Field(None, ge=15, le=43200, description="Link expiration time in minutes (15-43200)")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateEmbeddedEditorResponse(BaseModel):
    """Response model for creating embedded editor."""

    editor_entity: str = Field(..., description="Type of editor entity: 'document' or 'document_group'")
    editor_url: str = Field(..., description="URL for the embedded editor")


class CreateEmbeddedSendingRequest(BaseModel):
    """Request model for creating embedded sending."""

    entity_id: str = Field(..., description="ID of the document or document group")
    entity_type: str | None = Field(None, description="Type of entity: 'document' or 'document_group'. If not provided, will be auto-detected")
    redirect_uri: str | None = Field(None, description="URL to redirect to after sending is complete")
    redirect_target: str | None = Field("self", description="Redirect target: 'self' for same tab, 'blank' for new tab")
    link_expiration: int | None = Field(None, ge=14, le=45, description="Link expiration time in days (14-45)")
    type: str | None = Field("manage", description="Specifies the sending step: 'manage' (default), 'edit', 'send-invite'")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateEmbeddedSendingResponse(BaseModel):
    """Response model for creating embedded sending."""

    sending_entity: str = Field(..., description="Type of sending entity: 'document', 'document_group', or 'invite'")
    sending_url: str = Field(..., description="URL for the embedded sending")


# Template to invite workflow models
class SendInviteFromTemplateRequest(BaseModel):
    """Request model for creating document/group from template and sending invite immediately."""

    entity_id: str = Field(..., description="ID of the template or template group")
    entity_type: str | None = Field(None, description="Type of entity: 'template' or 'template_group' (optional)")
    name: str | None = Field(None, description="Optional name for the new document or document group")
    folder_id: str | None = Field(None, description="Optional ID of the folder to store the document group")
    orders: list[InviteOrder] = Field(default=[], description="List of orders with recipients for the invite")


class SendInviteFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and sending invite immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    invite_id: str = Field(..., description="ID of the created invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")


# Template to embedded sending workflow models
class CreateEmbeddedSendingFromTemplateRequest(BaseModel):
    """Request model for creating document/group from template and creating embedded sending immediately."""

    entity_id: str = Field(..., description="ID of the template or template group")
    entity_type: str | None = Field(None, description="Type of entity: 'template' or 'template_group' (optional)")
    name: str | None = Field(None, description="Optional name for the new document or document group")
    redirect_uri: str | None = Field(None, description="Optional redirect URI after completion")
    redirect_target: str | None = Field(None, description="Optional redirect target: 'self', 'blank', or 'self' (default)")
    link_expiration: int | None = Field(None, ge=14, le=45, description="Optional link expiration in days (14-45)")
    type: str | None = Field(None, description="Type of sending step: 'manage', 'edit', or 'send-invite'")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateEmbeddedSendingFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and creating embedded sending immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    sending_id: str = Field(..., description="ID of the created embedded sending")
    sending_entity: str = Field(..., description="Type of sending entity: 'document', 'document_group', or 'invite'")
    sending_url: str = Field(..., description="URL for the embedded sending")


class CreateEmbeddedEditorFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and creating embedded editor immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    editor_id: str = Field(..., description="ID of the created embedded editor")
    editor_entity: str = Field(..., description="Type of editor entity: 'document' or 'document_group'")
    editor_url: str = Field(..., description="URL for the embedded editor")


# Template to embedded invite workflow models
class CreateEmbeddedInviteFromTemplateRequest(BaseModel):
    """Request model for creating document/group from template and creating embedded invite immediately."""

    entity_id: str = Field(..., description="ID of the template or template group")
    entity_type: str | None = Field(None, description="Type of entity: 'template' or 'template_group' (optional)")
    name: str | None = Field(None, description="Optional name for the new document or document group")
    orders: list[EmbeddedInviteOrder] = Field(default=[], description="List of orders with recipients for the embedded invite")
    redirect_uri: str | None = Field(None, description="Optional redirect URI after completion")
    redirect_target: str | None = Field(None, description="Optional redirect target: 'self', 'blank', or 'self' (default)")
    link_expiration: int | None = Field(None, ge=15, le=43200, description="Optional link expiration in minutes (15-43200)")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateEmbeddedInviteFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and creating embedded invite immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    invite_id: str = Field(..., description="ID of the created embedded invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")
    recipient_links: list[dict[str, str]] = Field(..., description="Array of objects with role and link for recipients with delivery_type='link'")


# Document group status models
class DocumentGroupStatusAction(BaseModel):
    """Action status within a document group invite step."""

    action: str = Field(..., description="Action type: 'view', 'sign', 'approve'")
    email: str = Field(..., description="Recipient's email address")
    document_id: str = Field(..., description="ID of the document")
    status: str = Field(..., description="Action status: 'created', 'pending', 'fulfilled'")
    role_name: str = Field(..., description="Role name for this action")


class DocumentGroupStatusStep(BaseModel):
    """Step status within a document group invite."""

    status: str = Field(..., description="Step status: 'created', 'pending', 'fulfilled'")
    order: int = Field(..., description="Step order number")
    actions: list[DocumentGroupStatusAction] = Field(..., description="List of actions in this step")


class InviteStatus(BaseModel):
    """Complete status information for an invite."""

    invite_id: str = Field(..., description="ID of the invite")
    status: str = Field(..., description="Overall invite status: 'created', 'pending', 'fulfilled'")
    steps: list[DocumentGroupStatusStep] = Field(..., description="List of steps in the invite")


class DocumentDownloadLinkResponse(BaseModel):
    """Response model for document download link."""

    link: str = Field(..., description="Download link for the document")


# Create from template models
class CreateFromTemplateRequest(BaseModel):
    """Request model for creating document/group from template."""

    entity_id: str = Field(..., description="ID of the template or template group")
    entity_type: str | None = Field(None, description="Type of entity: 'template' or 'template_group' (optional)")
    name: str | None = Field(None, description="Optional name for the new document or document group")


class CreateFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template."""

    entity_id: str = Field(..., description="ID of the created document or document group")
    entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    name: str = Field(..., description="Name of the created entity")


class UploadDocumentResponse(BaseModel):
    """Response model for uploading document."""

    document_id: str = Field(..., description="ID of the uploaded document")
    filename: str = Field(..., description="Name of the uploaded file")
    check_fields: bool = Field(..., description="Whether fields were checked in the document")


class FieldToUpdate(BaseModel):
    """Single field to update in a document."""

    name: str = Field(..., description="Name of the field to update")
    value: str = Field(..., description="New value for the field")


class UpdateDocumentFields(BaseModel):
    """Request model for updating document fields."""

    document_id: str = Field(..., description="ID of the document to update")
    fields: list[FieldToUpdate] = Field(..., description="Array of fields to update with their new values")


class UpdateDocumentFieldsResult(BaseModel):
    """Result of updating document fields."""

    document_id: str = Field(..., description="ID of the document that was updated")
    updated: bool = Field(..., description="Whether the document fields were successfully updated")
    reason: str | None = Field(None, description="Reason for failure if updated is false")


class UpdateDocumentFieldsResponse(BaseModel):
    """Response model for updating document fields."""

    results: list[UpdateDocumentFieldsResult] = Field(..., description="Array of update results for each document")
