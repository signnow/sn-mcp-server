"""
SignNow API Data Models - Document Groups and Template Groups

Pydantic models for SignNow API responses and requests related to document groups and template groups.
"""

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class DocumentGroupTemplate(BaseModel):
    """Single item of the `document_group_templates` array."""

    folder_id: str | None = Field(None, description="Folder ID, if the group is stored in a folder")
    last_updated: int = Field(..., description="Unix timestamp of the last update")
    template_group_id: str = Field(..., description="Document-group template ID")
    template_group_name: str = Field(..., description="Name of the template group")
    owner_email: EmailStr = Field(..., description="Owner of the template group")
    templates: list[dict[str, Any]] = Field(..., description="Templates in this group")
    is_prepared: bool = Field(..., description="Whether the group is ready for sending")


class DocumentGroupTemplatesResponse(BaseModel):
    """Full JSON response from `/user/documentgroup/templates`."""

    document_group_templates: list[DocumentGroupTemplate]
    document_group_template_total_count: int = Field(..., description="Total number of template groups in the response")


class DocumentGroupDocument(BaseModel):
    """Document information within a document group."""

    id: str = Field(..., description="Document ID")
    document_name: str = Field(..., description="Document name")
    thumbnail: dict[str, str] = Field(..., description="Document thumbnails")
    roles: list[str] = Field(..., description="Roles defined for this document")


class DocumentGroup(BaseModel):
    """Single document group from the `/user/documentgroups` endpoint."""

    last_updated: int = Field(..., description="Unix timestamp of the last update")
    group_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    invite_id: str | None = Field(None, description="Invite ID for this group")
    invite_status: str | None = Field(None, description="Status of the invite (e.g., 'pending')")
    documents: list[DocumentGroupDocument] = Field(..., description="List of documents in this group")


class DocumentGroupsResponse(BaseModel):
    """Full JSON response from `/user/documentgroups`."""

    document_groups: list[DocumentGroup]
    document_group_total_count: int = Field(..., description="Total number of document groups")


class CreateDocumentGroupRequest(BaseModel):
    """Request model for creating document group."""

    document_ids: list[str] = Field(..., description="Array of document IDs to group together")
    group_name: str = Field(..., description="Name for the document group")


class CreateDocumentGroupResponse(BaseModel):
    """Response model for creating document group."""

    id: str = Field(..., description="ID of the created document group")


class CreateDocumentGroupTemplateRequest(BaseModel):
    """Request model for creating document group template."""

    name: str = Field(..., description="Document group template name")
    folder_id: str | None = Field(None, description="ID of the templates folder")


class CreateDocumentGroupTemplateResponse(BaseModel):
    """Response model for creating document group template."""

    data: dict[str, str] = Field(..., description="Document group template ID")


class CreateDocumentGroupTemplateFromGroupRequest(BaseModel):
    """Request model for creating document group template from document group."""

    name: str = Field(..., description="Name for the new document group template")
    folder_id: str | None = Field(None, description="Folder where to save the template (must be Templates folder or subfolder)")


class AddTemplateToDocumentGroupTemplateRequest(BaseModel):
    """Request model for adding template to document group template."""

    document_id: str | None = Field(None, description="ID of the document to add")
    template_id: str | None = Field(None, description="ID of the template to add")


class AddTemplateToDocumentGroupTemplateResponse(BaseModel):
    """Response model for adding template to document group template."""

    data: dict[str, str] = Field(..., description="ID of the added template")


class CreateDocumentGroupFromTemplateRequest(BaseModel):
    """Request model for creating document group from template."""

    group_name: str = Field(..., description="Name of the document group")
    client_timestamp: str | None = Field(None, description="Timestamp of client")
    folder_id: str | None = Field(None, description="ID of the folder")


class DocumentGroupTemplateDocument(BaseModel):
    """Document in document group template."""

    id: str = Field(..., description="Document ID")
    role: str = Field(..., description="Recipient's role name")
    action: str = Field(..., description="Allowed action: 'view', 'sign', 'approve'")


class DocumentGroupTemplateRecipientReminder(BaseModel):
    """Reminder settings for document group template recipient."""

    remind_after: int | None = Field(None, description="Send reminder after specified days")
    remind_before: int | None = Field(None, description="Send reminder before expiration")
    remind_repeat: int | None = Field(None, description="Send reminder every specified days")


class DocumentGroupTemplateRecipientAuthentication(BaseModel):
    """Authentication settings for document group template recipient."""

    type: str = Field(..., description="Authentication type: 'phone' or 'password'")
    value: str | None = Field(None, description="Password value for password authentication")
    phone: str | None = Field(None, description="Phone number for phone authentication")
    method: str | None = Field(None, description="Method for phone: 'sms' or 'phone_call'")
    sms_message: str | None = Field(None, description="Custom SMS message with {password} placeholder")


class DocumentGroupTemplateRecipientAttributes(BaseModel):
    """Attributes for document group template recipient."""

    message: str | None = Field(None, description="Invite email message")
    subject: str | None = Field(None, description="Invite email subject")
    expiration_days: int | None = Field(None, description="Days until invite expires (3-180)")
    reminder: DocumentGroupTemplateRecipientReminder | None = Field(None, description="Reminder email settings")
    allow_forwarding: bool | None = Field(None, description="Allow recipients to reassign invite")
    i_am_recipient: bool | None = Field(None, description="Document sender is also recipient")
    show_decline_button: bool | None = Field(None, description="Show decline button on signature fields")
    redirect_uri: str | None = Field(None, description="URL after recipient completes document")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' or 'self'")
    decline_redirect_uri: str | None = Field(None, description="URL after recipient declines document")
    close_redirect_uri: str | None = Field(None, description="URL after save progress or close")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class DocumentGroupTemplateRecipient(BaseModel):
    """Recipient in document group template."""

    name: str = Field(..., description="Recipient's name")
    email: str | None = Field(None, description="Recipient's email address")
    order: int = Field(..., description="Recipient's order of signing")
    documents: list[DocumentGroupTemplateDocument] = Field(..., description="List of documents and roles")
    attributes: DocumentGroupTemplateRecipientAttributes | None = Field(None, description="Recipient attributes")


class UnmappedDocument(BaseModel):
    """Unmapped document in document group template."""

    id: str = Field(..., description="Document ID")
    role: str = Field(..., description="Recipient's role name")
    action: str = Field(..., description="Allowed action")


class AllowedUnmappedSignDocument(BaseModel):
    """Allowed unmapped sign document."""

    id: str = Field(..., description="Document ID")
    role: str = Field(..., description="Recipient's role name")
    recipient: str = Field(..., description="Recipient's name")


class GetDocumentGroupTemplateRecipientsResponse(BaseModel):
    """Response model for getting document group template recipients."""

    data: dict[str, Any] = Field(..., description="Recipients data including recipients, unmapped documents, and cc")


class EditDocumentGroupTemplateRecipientsRequest(BaseModel):
    """Request model for editing document group template recipients."""

    recipients: list[DocumentGroupTemplateRecipient] = Field(..., description="List of recipients")
    unmapped_documents: list[UnmappedDocument] | None = Field(None, description="List of unmapped documents")
    allowed_unmapped_sign_documents: list[AllowedUnmappedSignDocument] | None = Field(None, description="List of allowed unmapped sign documents")
    cc: list[str] | None = Field(None, description="List of cc recipient emails (max 100)")


class CreateDocumentGroupFromTemplateResponse(BaseModel):
    """Response model for creating document group from template."""

    data: dict[str, Any] = Field(..., description="Created document group data")


# Embedded models for document groups
class CreateDocumentGroupEmbeddedEditorRequest(BaseModel):
    """Request model for creating document group embedded editor link."""

    redirect_uri: str | None = Field(None, description="Link that opens after editing the document group")
    link_expiration: int | None = Field(15, description="Link expiration in minutes (default: 15, max: 43200 for Admin users)")
    redirect_target: str | None = Field("self", description="Redirect target: 'blank' (new tab) or 'self' (same tab)")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateDocumentGroupEmbeddedSendingRequest(BaseModel):
    """Request model for creating document group embedded sending link."""

    redirect_uri: str | None = Field(None, description="Page that opens after embedded sending has been set up")
    redirect_target: str | None = Field("self", description="Redirect target: 'blank' (new tab) or 'self' (same tab)")
    link_expiration: int | None = Field(15, description="Link expiration in minutes (15-45, max: 43200 for Admin users)")
    type: str | None = Field("manage", description="Sending step: 'manage' (Add documents), 'edit' (editor), 'send-invite' (Send Invite page)")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class GetDocumentGroupResponse(BaseModel):
    """Response model for getting a single document group."""

    id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    invite_id: str | None = Field(None, description="Invite ID for this group")
    documents: list[DocumentGroupDocument] = Field(..., description="List of documents in this group")
    originator_organization_settings: list[dict[str, Any]] = Field(..., description="Organization settings for the originator")


# V2 Document Group models
class DocumentGroupV2Owner(BaseModel):
    """Owner information in v2 document group response."""

    id: str = Field(..., description="Owner ID")
    email: str = Field(..., description="Owner email")
    organization: dict[str, str] = Field(..., description="Organization info with ID")


class DocumentGroupV2Thumbnail(BaseModel):
    """Thumbnail URLs for document in v2 response."""

    small: str = Field(..., description="Small thumbnail URL")
    medium: str = Field(..., description="Medium thumbnail URL")
    large: str = Field(..., description="Large thumbnail URL")


class DocumentGroupV2EmailStatus(BaseModel):
    """Email status for field invite in v2 response."""

    status: str = Field(..., description="Email status (e.g., 'sent')")
    created_at: int = Field(..., description="Unix timestamp when status was created")
    last_reaction_at: int = Field(..., description="Unix timestamp of last reaction")


class DocumentGroupV2EmailGroup(BaseModel):
    """Email group information in v2 response."""

    id: str | None = Field(None, description="Email group ID")
    name: str | None = Field(None, description="Email group name")


class DocumentGroupV2FieldInvite(BaseModel):
    """Field invite information in v2 response."""

    id: str = Field(..., description="Field invite ID")
    created: int = Field(..., description="Unix timestamp when invite was created")
    updated: int = Field(..., description="Unix timestamp when invite was updated")
    status: str = Field(..., description="Invite status (e.g., 'pending')")
    expiration_time: int = Field(..., description="Unix timestamp when invite expires")
    expiration_days: int = Field(..., description="Number of days until expiration")
    signer_email: str = Field(..., description="Email of the signer")
    password_protected: str = Field(..., description="Whether invite is password protected ('1' or '0')")
    email_group: DocumentGroupV2EmailGroup | None = Field(None, description="Email group if used")
    email_statuses: list[DocumentGroupV2EmailStatus] = Field(..., description="List of email statuses")


class DocumentGroupV2DocumentOwner(BaseModel):
    """Document owner information in v2 response."""

    id: str = Field(..., description="Document owner ID")
    email: str = Field(..., description="Document owner email")


class DocumentGroupV2Document(BaseModel):
    """Document information in v2 document group response."""

    roles: list[str] = Field(..., description="List of roles for this document")
    document_name: str = Field(..., description="Name of the document")
    id: str = Field(..., description="Document ID")
    updated: int = Field(..., description="Unix timestamp when document was last updated")
    field_invites: list[DocumentGroupV2FieldInvite] = Field(..., description="List of field invites for this document")


class DocumentGroupV2FreeformInvite(BaseModel):
    """Freeform invite information in v2 response."""

    id: str | None = Field(None, description="Freeform invite ID")
    last_id: str | None = Field(None, description="Last freeform invite ID")


class DocumentGroupV2Data(BaseModel):
    """Document group data in v2 response."""

    id: str = Field(..., description="Document group ID")
    name: str = Field(..., description="Document group name")
    created: int = Field(..., description="Unix timestamp when group was created")
    invite_id: str | None = Field(None, description="Current invite ID")
    pending_step_id: str | None = Field(None, description="ID of the pending step")
    state: str = Field(..., description="Current state of the document group (e.g., 'pending')")
    last_invite_id: str | None = Field(None, description="ID of the last invite")
    documents: list[DocumentGroupV2Document] = Field(..., description="List of documents in the group")


class GetDocumentGroupV2Response(BaseModel):
    """Response model for getting a single document group using v2 endpoint."""

    data: DocumentGroupV2Data = Field(..., description="Document group data as returned by v2 endpoint")
