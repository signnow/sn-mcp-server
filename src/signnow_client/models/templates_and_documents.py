"""
SignNow API Data Models - Templates and Documents

Pydantic models for SignNow API responses and requests related to templates and documents.
"""

from typing import Any

from pydantic import BaseModel, Field, HttpUrl


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
    roles: list[str] = Field(..., description="Roles defined for this template")


class DocumentThumbnail(BaseModel):
    """Document thumbnail URLs."""

    small: str = Field(..., description="Small thumbnail URL")
    medium: str = Field(..., description="Medium thumbnail URL")
    large: str = Field(..., description="Large thumbnail URL")


class DocumentSignature(BaseModel):
    """Document signature information."""

    id: str = Field(..., description="Signature ID")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="Signer email")
    page_number: str = Field(..., description="Page number")
    width: str = Field(..., description="Signature width")
    height: str = Field(..., description="Signature height")
    x: str = Field(..., description="X coordinate")
    y: str = Field(..., description="Y coordinate")
    created: str = Field(..., description="Creation timestamp")
    data: str = Field(..., description="Signature data")


class DocumentFieldJsonAttributes(BaseModel):
    """Document field JSON attributes."""

    name: str = Field(..., description="Field name")
    prefilled_text: str | None = Field(None, description="Prefilled text")


class DocumentField(BaseModel):
    """Document field information."""

    id: str = Field(..., description="Field ID")
    type: str = Field(..., description="Field type")
    role_id: str = Field(..., description="Role ID")
    json_attributes: DocumentFieldJsonAttributes = Field(..., description="Field attributes")
    role: str = Field(..., description="Role name")
    originator: str = Field(..., description="Originator email")
    fulfiller: str | None = Field(None, description="Fulfiller email")
    field_request_canceled: str | None = Field(None, description="Field request canceled")
    template_field_id: str | None = Field(None, description="Template field ID")
    field_id: str | None = Field(..., description="Field ID")


class DocumentRole(BaseModel):
    """Document role information."""

    unique_id: str = Field(..., description="Role unique ID")
    signing_order: str = Field(..., description="Signing order")
    name: str = Field(..., description="Role name")


class DocumentPage(BaseModel):
    """Document page information."""

    src: str = Field(..., description="Page source URL")
    size: dict[str, int] = Field(..., description="Page size")


# Document field invite models (detailed from /document endpoint)
class DocumentFieldInviteEmailGroup(BaseModel):
    """Email group information in document field invite."""

    id: str = Field(..., description="Email group ID")
    name: str = Field(..., description="Email group name")


class DocumentFieldInviteStatus(BaseModel):
    """Detailed field invite information from document endpoint."""

    id: str = Field(..., description="Field invite ID")
    status: str = Field(..., description="Invite status: 'fulfilled', 'pending', 'created'")
    created: str = Field(..., description="Creation timestamp")
    email: str = Field(..., description="Recipient email address")
    role: str = Field(..., description="Role name")
    reminder: str = Field(..., description="Reminder setting ('0' or '1')")
    updated: str = Field(..., description="Last update timestamp")
    role_id: str = Field(..., description="Role ID")
    declined: list[dict[str, Any]] = Field(..., description="Declined information")


class DocumentResponse(BaseModel):
    """Response model for getting document."""

    id: str = Field(..., description="Document ID")
    user_id: str = Field(..., description="User ID")
    document_name: str = Field(..., description="Document name")
    page_count: str = Field(..., description="Page count")
    created: str = Field(..., description="Creation timestamp")
    updated: str = Field(..., description="Update timestamp")
    original_filename: str = Field(..., description="Original filename")
    origin_document_id: str | None = Field(None, description="Origin document ID")
    owner: str = Field(..., description="Owner email")
    template: bool = Field(..., description="Template status")
    thumbnail: DocumentThumbnail = Field(..., description="Document thumbnails")
    signatures: list[DocumentSignature] = Field(..., description="Document signatures")
    seals: list[dict[str, Any]] = Field(..., description="Document seals")
    texts: list[dict[str, Any]] = Field(..., description="Document texts")
    checks: list[dict[str, Any]] = Field(..., description="Document checks")
    inserts: list[dict[str, Any]] = Field(..., description="Document inserts")
    tags: list[dict[str, str]] = Field(..., description="Document tags")
    fields: list[DocumentField] = Field(..., description="Document fields")
    requests: list[dict[str, Any]] = Field(..., description="Document requests")
    notary_invites: list[dict[str, Any]] = Field(..., description="Notary invites")
    roles: list[DocumentRole] = Field(..., description="Document roles")
    field_invites: list[DocumentFieldInviteStatus] = Field(..., description="Field invites")
    version_time: str = Field(..., description="Version timestamp")
    enumeration_options: list[dict[str, Any]] = Field(..., description="Enumeration options")
    attachments: list[dict[str, Any]] = Field(..., description="Document attachments")
    routing_details: list[dict[str, Any]] = Field(..., description="Routing details")
    integrations: list[dict[str, Any]] = Field(..., description="Integrations")
    hyperlinks: list[dict[str, Any]] = Field(..., description="Hyperlinks")
    radiobuttons: list[dict[str, Any]] = Field(..., description="Radio buttons")
    document_group_template_info: list[dict[str, Any]] = Field(..., description="Document group template info")
    originator_organization_settings: list[dict[str, str]] = Field(..., description="Originator organization settings")
    document_group_info: dict[str, Any] = Field(..., description="Document group info")
    parent_id: str = Field(..., description="Parent ID")
    originator_logo: str = Field(..., description="Originator logo")
    pages: list[DocumentPage] = Field(..., description="Document pages")
    lines: list[dict[str, Any]] = Field(..., description="Document lines")


class DocumentFieldData(BaseModel):
    """Document field data."""

    id: str = Field(..., description="Field ID")
    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Field type")
    value: str | None = Field(None, description="Field value")


class GetDocumentFieldsResponse(BaseModel):
    """Response model for getting document fields."""

    data: list[DocumentFieldData] = Field(..., description="Document fields data")


class DocumentHistoryEvent(BaseModel):
    """Document history event."""

    unique_id: str = Field(..., description="Event unique ID")
    event: str = Field(..., description="Event type")
    user_id: str = Field(..., description="User ID")
    document_id: str = Field(..., description="Document ID")
    client_app_name: str = Field(..., description="Client application name")
    ip_address: str = Field(..., description="IP address")
    email: str = Field(..., description="User email")
    field_id: str | None = Field(None, description="Field ID")
    element_id: str | None = Field(None, description="Element ID")
    json_attributes: str | None = Field(None, description="JSON attributes")
    client_timestamp: int | None = Field(None, description="Client timestamp")
    created: int = Field(..., description="Creation timestamp")
    origin: str | None = Field(None, description="Origin")


class EmailHistoryEvent(BaseModel):
    """Email history event."""

    subject: str = Field(..., description="Email subject")
    message: str = Field(..., description="Email message")
    event_type: str = Field(..., description="Event type")
    json_attributes: str = Field(..., description="JSON attributes")
    created: int = Field(..., description="Creation timestamp")


class GetDocumentHistoryResponse(BaseModel):
    """Response model for getting document history."""

    document_history: list[DocumentHistoryEvent] = Field(..., description="Document history events")
    email_history_events: list[EmailHistoryEvent] | None = Field(None, description="Email history events")


class FolderDocument(BaseModel):
    """Folder document information."""

    id: str = Field(..., description="Document ID")
    user_id: str = Field(..., description="User ID")
    document_name: str = Field(..., description="Document name")
    page_count: str = Field(..., description="Page count")
    created: str = Field(..., description="Creation timestamp")
    updated: str = Field(..., description="Update timestamp")
    original_filename: str = Field(..., description="Original filename")
    origin_document_id: str | None = Field(None, description="Origin document ID")
    owner: str = Field(..., description="Owner email")
    origin_user_id: str | None = Field(None, description="Origin user ID")
    thumbnail: DocumentThumbnail | None = Field(None, description="Document thumbnail")
    template: bool = Field(..., description="Template status")
    is_favorite: bool = Field(..., description="Favorite status")
    signatures: list[DocumentSignature] = Field(..., description="Document signatures")
    seals: list[dict[str, Any]] = Field(..., description="Document seals")
    texts: list[dict[str, Any]] = Field(..., description="Document texts")
    checks: list[dict[str, Any]] = Field(..., description="Document checks")
    inserts: list[dict[str, Any]] = Field(..., description="Document inserts")
    tags: list[dict[str, str]] = Field(..., description="Document tags")
    fields: list[DocumentField] = Field(..., description="Document fields")
    requests: list[dict[str, Any]] = Field(..., description="Document requests")
    notary_invites: list[dict[str, Any]] = Field(..., description="Notary invites")
    roles: list[DocumentRole] = Field(..., description="Document roles")
    field_invites: list[dict[str, Any]] = Field(..., description="Field invites")
    version_time: str = Field(..., description="Version timestamp")
    enumeration_options: list[dict[str, Any]] = Field(..., description="Enumeration options")
    attachments: list[dict[str, Any]] = Field(..., description="Document attachments")
    exported_to: list[dict[str, Any]] = Field(..., description="Export information")
    parent_id: str = Field(..., description="Parent ID")
    entity_labels: list[dict[str, Any]] = Field(..., description="Entity labels")


class CreateDocumentFromUrlRequest(BaseModel):
    """Request model for creating document from URL."""

    url: str = Field(..., description="URL of the file to create document from")
    check_fields: bool | None = Field(True, description="Whether to check for fields in the document")


class CreateDocumentFromUrlResponse(BaseModel):
    """Response model for creating document from URL."""

    id: str = Field(..., description="ID of the created document")


class CreateTemplateRequest(BaseModel):
    """Request model for creating template from document."""

    document_id: str = Field(..., description="ID of the document which is the source of a template")
    document_name: str = Field(..., description="The new template name")


class CreateTemplateResponse(BaseModel):
    """Response model for creating template."""

    id: str = Field(..., description="ID of the created template")


class CreateDocumentFromTemplateRequest(BaseModel):
    """Request model for creating document from template."""

    document_name: str | None = Field(None, description="Name for the new document (defaults to original template name)")


class CreateDocumentFromTemplateResponse(BaseModel):
    """Response model for creating document from template."""

    id: str = Field(..., description="ID of the created document")
    document_name: str | None = Field(None, description="Name of the created document")


class MergeDocumentsRequest(BaseModel):
    """Request model for merging documents."""

    name: str = Field(..., description="Name of the merged document")
    document_ids: list[str] = Field(..., description="IDs of documents to merge")
    upload_document: bool | None = Field(False, description="Upload merged document to documents list")


class MergeDocumentsResponse(BaseModel):
    """Response model for merging documents."""

    document_id: str = Field(..., description="ID of the merged document")


class PrefillTextField(BaseModel):
    """Single text field to prefill."""

    field_name: str = Field(..., description="Name of the field to prefill")
    prefilled_text: str = Field(..., description="Text to prefill in the field")


class PrefillTextFieldsRequest(BaseModel):
    """Request model for prefill text fields."""

    fields: list[PrefillTextField] = Field(..., description="Array of fields to prefill with text")


# Embedded models for documents
class DocumentEmbeddedInviteAuthentication(BaseModel):
    """Authentication settings for document embedded invite."""

    type: str = Field(..., description="Authentication type: 'phone' or 'password'")
    password: str | None = Field(None, description="Password for password authentication")
    method: str | None = Field(None, description="Method for phone authentication: 'sms' or 'phone_call'")
    phone: str | None = Field(None, description="Phone number for phone authentication")
    sms_message: str | None = Field(None, description="Custom SMS message with {password} placeholder")


class DocumentEmbeddedInviteSignature(BaseModel):
    """QES signature settings for document embedded invite."""

    type: str = Field(..., description="Type of QES: 'eideasy' or 'nom151'")


class DocumentEmbeddedInvite(BaseModel):
    """Individual invite for document embedded signing."""

    email: str = Field(..., description="Email address of the recipient")
    role_id: str = Field(..., description="Recipient's role ID")
    order: int = Field(..., description="The order of signing")
    language: str | None = Field(None, description="Language of signing session: 'en', 'es', 'fr'")
    auth_method: str = Field(..., description="Authentication method within integrated application")
    first_name: str | None = Field(None, description="Signer's first name")
    last_name: str | None = Field(None, description="Signer's last name")
    required_preset_signature_name: str | None = Field(None, description="Prefilled signature name, disabled for editing")
    prefill_signature_name: str | None = Field(None, description="Editable signature name for signer")
    force_new_signature: int | None = Field(None, description="Force new signature (1) or allow saved (0)")
    redirect_uri: str | None = Field(None, description="Link after signing completion")
    decline_redirect_uri: str | None = Field(None, description="Link after signing decline")
    close_redirect_uri: str | None = Field(None, description="Link after save progress or close")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' or 'self'")
    authentication: DocumentEmbeddedInviteAuthentication | None = Field(None, description="Authentication settings")
    delivery_type: str | None = Field("link", description="Delivery type: 'email' or 'link'")
    subject: str | None = Field(None, description="Invite email subject (max 1000 chars)")
    message: str | None = Field(None, description="Invite email message (max 5000 chars)")
    link_expiration: int | None = Field(None, description="Email invite expiration in minutes (15-43200)")
    session_expiration: int | None = Field(None, description="Signing session expiration in minutes (15-1440)")
    signature: DocumentEmbeddedInviteSignature | None = Field(None, description="QES signature settings")


class CreateDocumentEmbeddedInviteRequest(BaseModel):
    """Request model for creating document embedded invite."""

    name_formula: str | None = Field(None, description="Formula for completed document name")
    invites: list[DocumentEmbeddedInvite] = Field(..., description="List of invites for signers")


class DocumentEmbeddedInviteResponse(BaseModel):
    """Response model for document embedded invite."""

    id: str = Field(..., description="ID of the created embedded invite")
    email: str = Field(..., description="Signer email")
    role_id: str = Field(..., description="Role ID")
    order: int = Field(..., description="Signing order")
    status: str = Field(..., description="Invite status")
    expires_at: int | None = Field(None, description="Expiration timestamp")
    link: str | None = Field(None, description="Generated link")
    redirect_uri: str | None = Field(None, description="Redirect URI")
    decline_redirect_uri: str | None = Field(None, description="Decline redirect URI")
    redirect_target: str | None = Field(None, description="Redirect target")


class CreateDocumentEmbeddedInviteResponse(BaseModel):
    """Response model for creating document embedded invite."""

    data: list[DocumentEmbeddedInviteResponse] = Field(..., description="List of created invites")


class GenerateDocumentEmbeddedInviteLinkRequest(BaseModel):
    """Request model for generating document embedded invite link."""

    auth_method: str = Field(..., description="Authentication method, must match the one specified when creating the invite")
    link_expiration: int | None = Field(None, description="Link expiration in minutes (15-45)")
    session_expiration: int | None = Field(None, description="Session expiration in minutes (15-1440)")


class GenerateDocumentEmbeddedInviteLinkResponse(BaseModel):
    """Response model for generating document embedded invite link."""

    data: dict[str, str] = Field(..., description="Generated link data")


class CreateDocumentEmbeddedEditorRequest(BaseModel):
    """Request model for creating document embedded editor link."""

    redirect_uri: str | None = Field(None, description="Page that opens after the editing session ends")
    link_expiration: int | None = Field(15, description="Link expiration in minutes (default: 15, max: 43200 for Admin users)")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' (new tab) or 'self' (same tab)")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class EmbeddedEditorData(BaseModel):
    """Data model for embedded editor response."""

    url: str = Field(..., description="Generated embedded editor URL")


class CreateEmbeddedEditorResponse(BaseModel):
    """Response model for creating embedded editor link."""

    data: EmbeddedEditorData = Field(..., description="Embedded editor data")


class CreateDocumentEmbeddedSendingRequest(BaseModel):
    """Request model for creating document embedded sending link."""

    type: str = Field(..., description="Type of invite settings: 'invite' (Send Invite page) or 'document' (editor + Send Invite page)")
    redirect_uri: str | None = Field(None, description="Page that opens after the signing session ends")
    link_expiration: str | None = Field("15", description="Link expiration in minutes (default: 15, max: 43200 for Admin users)")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' (new tab) or 'self' (same tab)")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class EmbeddedSendingData(BaseModel):
    """Data model for embedded sending response."""

    url: str = Field(..., description="Generated embedded sending URL")


class CreateEmbeddedSendingResponse(BaseModel):
    """Response model for creating embedded sending link."""

    data: EmbeddedSendingData = Field(..., description="Generated embedded sending URL(s)")


class EmbeddedSendingError(BaseModel):
    """Error model for embedded sending operations."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


class EmbeddedSendingErrorResponse(BaseModel):
    """Error response model for embedded sending operations."""

    errors: list[EmbeddedSendingError] = Field(..., description="List of errors")


# Document field invite models
class DocumentFieldInviteReminder(BaseModel):
    """Reminder settings for document field invite recipient."""

    remind_after: int | None = Field(None, description="x days after the invite, a recipient gets a reminder email. Must be less than expiration_days", ge=1, le=179)
    remind_before: int | None = Field(None, description="x days before expiration, a recipient gets a reminder email. Must be less than expiration_days", ge=1, le=179)
    remind_repeat: int | None = Field(None, description="A recipient gets a reminder email each x days after the invite is sent", ge=1, le=7)


class DocumentFieldInviteAuthentication(BaseModel):
    """Authentication settings for document field invite recipient."""

    type: str = Field(..., description="Type of signer's identity verification. Possible values: 'password' or 'phone'")
    password: str | None = Field(None, description="Signer's verification password. Required if 'authentication_type': 'password'")
    phone: str | None = Field(None, description="Signer's verification phone number. Required if 'authentication_type': 'phone'")
    method: str | None = Field("sms", description="Method of the phone authentication type. Required with the 'phone' authentication type. Allowed values: 'sms', 'phone_call'")
    authentication_sms_message: str | None = Field(None, description="If 'method': 'sms' - custom message, max 140 characters. Example: 'Custom SMS message to add to your {password}'")


class DocumentFieldInviteSignature(BaseModel):
    """QES signature settings for document field invite recipient."""

    type: str = Field(..., description="Type of QES signature. Possible values: 'eideasy', 'eideasy-pdf', and 'nom151'. All signers in the invite must have the same signature type")


class DocumentFieldInviteRecipient(BaseModel):
    """Recipient for document field invite."""

    email: str | None = Field(None, description="Recipient's email address")
    email_group: DocumentFieldInviteEmailGroup | None = Field(
        None,
        description="A group of users that should receive the invite. When one of the users signs the document, the document is completed. Must be used with the 'email_groups' array. Required if 'email' or 'phone_invite' is not added but cannot be used at the same time with either of these parameters",
    )
    phone_invite: str | None = Field(None, description="Recipient's phone number. Required for Invite via SMS")
    role_id: str | None = Field(None, description="ID of the recipient's Signer role. Optional if the role parameter is specified")
    role: str = Field(..., description="Recipient's Signer role name. e.g. Signer 1, Signer 2. Optional if the role_id parameter is specified")
    order: int = Field(
        ...,
        description="Integer, order of signing: 1 - the recipient has to sign the document first, then the document is sent to 2,3 etc. Several recipients can hold the same order of signing",
    )
    prefill_signature_name: str | None = Field(None, description="Prefilled text in the Signature field, available for editing by signer")
    required_preset_signature_name: str | None = Field(None, description="Prefilled text in the Signature field, disabled for editing by signer")
    force_new_signature: int | None = Field(
        None, description="Whether or not the signer can use their saved signature. Possible values: 0 - signer can use a saved signature, 1 - signer has to add a new signature"
    )
    reassign: str | None = Field(
        None,
        description="Specifies whether the recipient can forward the invite to another email address. '0' - recipient can forward the invite. '1' - recipient cannot forward the invite",
    )
    decline_by_signature: str | None = Field(None, description="Whether or not to allow recipients decline the invite")
    reminder: DocumentFieldInviteReminder | None = Field(None, description="Reminder email settings")
    expiration_days: int | None = Field(30, description="In x days, the invite expires", ge=3, le=180)
    authentication_type: str | None = Field(None, description="Type of signer's identity verification. Possible values: 'password' or 'phone'")
    password: str | None = Field(None, description="Signer's verification password. Required if 'authentication_type': 'password'")
    phone: str | None = Field(None, description="Signer's verification phone number. Required if 'authentication_type': 'phone'")
    method: str | None = Field("sms", description="Method of the phone authentication type. Required with the 'phone' authentication type. Allowed values: 'sms', 'phone_call'")
    authentication_sms_message: str | None = Field(None, description="If 'method': 'sms' - custom message, max 140 characters. Example: 'Custom SMS message to add to your {password}'")
    subject: str | None = Field(None, description="Custom email subject for the recipient")
    message: str | None = Field(None, description="Custom email message for the recipient")
    redirect_uri: str | None = Field(None, description="When all the requested fields are completed and signed, the signer is redirected to this URI")
    redirect_target: str | None = Field(
        None,
        description="Determines whether to open the redirect link in the new tab in the browser, or in the same tab after the signing session. Possible values: 'blank' - opens the link in the new tab, 'self' - opens the link in the same tab",
    )
    decline_redirect_uri: str | None = Field(None, description="The link that opens after the signing session has been declined by the signer")
    close_redirect_uri: str | None = Field(None, description="The link that opens when a signer clicks 'Save Progress and Finish Later' during a signing session or 'Close' in view mode")
    is_finish_redirect_canceled: bool | None = Field(
        False,
        description="Specifies whether the completion redirect setting is canceled for the organization. 'true' – the redirect is canceled; 'false' – the redirect remains active",
    )
    is_close_redirect_canceled: bool | None = Field(
        False,
        description="Specifies whether the save progress redirect setting is canceled for the organization. 'true' – the redirect is canceled; 'false' – the redirect remains active",
    )
    is_decline_redirect_canceled: bool | None = Field(
        False,
        description="Specifies whether the decline redirect setting is canceled for the organization. 'true' – the redirect is canceled; 'false' – the redirect remains active",
    )
    language: str | None = Field(
        None,
        description="Sets the language of the signing session and notification emails for the signer. Possible values: 'en' for English, 'es' for Spanish, and 'fr' for French. If not set, the language is determined by the language of your SignNow account. If emails are branded, you can set up your own email texts in different languages",
    )
    signature: DocumentFieldInviteSignature | None = Field(
        None,
        description="This object is used to request QES signatures from signers. To use it, a user must be a member of an organization with QES settings enabled. If QES is used, it must be used for all signers in the invite",
    )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateDocumentFieldInviteRequest(BaseModel):
    """Request model for creating document field invite."""

    document_id: str = Field(..., description="Path parameter: ID of the document")
    to: list[DocumentFieldInviteRecipient] = Field(..., description="Array[object]: email addresses and settings for all recipients")
    from_: str | None = Field(None, alias="from", description="Sender's email address: you can use only the email address associated with your SignNow account (login email) as 'from' address")
    subject: str | None = Field(None, description="Email subject for all signers")
    message: str | None = Field(None, description="Email message for all signers")
    cc_subject: str | None = Field(None, description="CC email subject for all CC recipients")
    cc_message: str | None = Field(None, description="CC email message for all CC recipients")


class CreateDocumentFieldInviteResponse(BaseModel):
    """Response model for creating document field invite."""

    status: str = Field(..., description="Status of the invite creation")


class CancelDocumentFieldInviteRequest(BaseModel):
    """Request model for canceling document field invite."""

    reason: str = Field(..., description="The reason for cancellation")


class CancelDocumentFieldInviteResponse(BaseModel):
    """Response model for canceling document field invite."""

    status: str = Field(..., description="Status of the invite cancellation")


# Field Invite models (for document field signing)
class FieldInviteReminder(BaseModel):
    """Reminder settings for field invite."""

    remind_after: int | None = Field(None, description="Days after invite to send reminder (1-179)")
    remind_before: int | None = Field(None, description="Days before expiration to send reminder (1-179)")
    remind_repeat: int | None = Field(None, description="Send reminder every X days (1-7)")


class FieldInviteEmailGroup(BaseModel):
    """Email group for field invite."""

    name: str = Field(..., description="Name of the contact group")


class FieldInviteEmail(BaseModel):
    """Email settings for field invite step."""

    email: str = Field(..., description="Recipient's email address")
    email_group: FieldInviteEmailGroup | None = Field(None, description="Contact group of recipients")
    subject: str | None = Field(None, description="Custom email subject for the recipient")
    message: str | None = Field(None, description="Custom email message for the recipient")
    reminder: FieldInviteReminder | None = Field(None, description="Reminder settings")
    expiration_days: int | None = Field(30, description="Days until invite expires (3-180)")


class FieldInviteAuthentication(BaseModel):
    """Authentication settings for field invite."""

    type: str = Field(..., description="Type of signer's identity verification: 'password' or 'phone'")
    value: str | None = Field(None, description="Password for password authentication or phone number for phone authentication")
    method: str | None = Field(None, description="Method for phone authentication: 'phone_call' or 'sms'")
    phone: str | None = Field(None, description="User's phone number for phone authentication")
    message: str | None = Field(None, description="Custom SMS message for SMS authentication (max 140 chars)")


class FieldInvitePaymentRequest(BaseModel):
    """Payment request details for field invite."""

    merchant_id: str = Field(..., description="ID of the merchant account added to your Organization")
    currency: str = Field(..., description="Payment currency requested")
    type: str = Field(..., description="Payment type, must be 'fixed'")
    amount: str = Field(..., description="Payment amount requested")


class FieldInviteSignature(BaseModel):
    """QES signature settings for field invite."""

    type: str = Field(..., description="Type of QES signature: 'eideasy', 'eideasy-pdf', or 'nom151'")


class FieldInviteAction(BaseModel):
    """Action definition for field invite step."""

    email: str | None = Field(None, description="Recipient's email address")
    email_group: FieldInviteEmailGroup | None = Field(None, description="Contact group of recipients")
    role_name: str = Field(..., description="Recipient's role name in the document")
    action: str = Field(..., description="Allowed action: 'view', 'sign', 'approve'")
    document_id: str = Field(..., description="ID of the document for this action")
    required_preset_signature_name: str | None = Field(None, description="Preset signature name, disabled for editing")
    allow_reassign: str | None = Field(None, description="Allow reassignment: '0' - not allowed, '1' - allowed")
    decline_by_signature: str | None = Field(None, description="Allow decline by signature: '0' - not allowed, '1' - allowed")
    authentication: FieldInviteAuthentication | None = Field(None, description="Signer identity verification")
    payment_request: FieldInvitePaymentRequest | None = Field(None, description="Payment request details")
    redirect_uri: str | None = Field(None, description="Link that opens after completion")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' for new tab, 'self' for same tab")
    decline_redirect_uri: str | None = Field(None, description="URL that opens after decline (for 'sign' action)")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Save Progress and Finish Later' or 'Close'")
    is_finish_redirect_canceled: bool | None = Field(False, description="Whether completion redirect is canceled")
    is_close_redirect_canceled: bool | None = Field(False, description="Whether save progress redirect is canceled")
    is_decline_redirect_canceled: bool | None = Field(False, description="Whether decline redirect is canceled")
    language: str | None = Field(None, description="Signing session and email language: 'en', 'es', 'fr'")
    signature: FieldInviteSignature | None = Field(None, description="QES signature settings")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class FieldInviteStep(BaseModel):
    """Single step in field invite workflow."""

    order: int = Field(..., description="Order of signing step")
    invite_emails: list[FieldInviteEmail] = Field(..., description="Email settings for this step")
    invite_actions: list[FieldInviteAction] = Field(..., description="Actions for this step")


class EmailGroup(BaseModel):
    """Email group definition for field invite."""

    id: str = Field(..., description="Signing group ID (40 characters if custom)")
    name: str = Field(..., description="Signing group name")
    emails: list[dict[str, str]] = Field(..., description="List of email addresses in the group")


class CompletionEmail(BaseModel):
    """Completion email settings for field invite."""

    email: str = Field(..., description="Email address of completion email recipient")
    disable_document_attachment: int | None = Field(None, description="Disable document attachment: 0 - enable, 1 - disable")
    subject: str | None = Field(None, description="Custom subject for completion email")
    message: str | None = Field(None, description="Custom message for completion email")


class CreateFieldInviteRequest(BaseModel):
    """Request model for creating field invite."""

    invite_steps: list[FieldInviteStep] = Field(..., description="Steps of the document group invite")
    email_groups: list[EmailGroup] | None = Field(None, description="Signing groups (required if using email_group)")
    completion_emails: list[CompletionEmail] | None = Field(None, description="Completion email settings")
    sign_as_merged: bool | None = Field(True, description="Send as merged document group")
    client_timestamp: int | None = Field(None, description="Timestamp of the document group invite")
    cc: list[str] | None = Field(None, description="Array of CC email addresses")
    cc_subject: str | None = Field(None, description="Common subject for CC emails")
    cc_message: str | None = Field(None, description="Common message for CC emails")


class CreateFieldInviteResponse(BaseModel):
    """Response model for creating field invite."""

    id: str = Field(..., description="ID of the created invite")
    pending_invite_link: str | None = Field(None, description="Pending invite link")


class FieldInviteActionStatus(BaseModel):
    """Status of a field invite action."""

    action: str = Field(..., description="Action type: 'view', 'sign', 'approve'")
    email: str | None = Field(None, description="Recipient's email")
    email_group: dict[str, str | None] | None = Field(None, description="Email group information")
    document_id: str = Field(..., description="Document ID")
    status: str = Field(..., description="Action status")
    role_name: str = Field(..., description="Role name")


class FieldInviteStepStatus(BaseModel):
    """Status of a field invite step."""

    id: str = Field(..., description="Step ID")
    status: str = Field(..., description="Step status")
    order: int = Field(..., description="Step order")
    actions: list[FieldInviteActionStatus] = Field(..., description="Actions in this step")


class FieldInviteStatus(BaseModel):
    """Field invite status information."""

    id: str = Field(..., description="Invite ID")
    status: str = Field(..., description="Invite status: 'created', 'pending', 'fulfilled'")
    steps: list[FieldInviteStepStatus] = Field(..., description="List of invite steps with their status")


class GetFieldInviteResponse(BaseModel):
    """Response model for getting field invite."""

    invite: FieldInviteStatus = Field(..., description="Invite information with id, status, and steps")


class SendEmailRequest(BaseModel):
    """Request model for sending document group email."""

    to: list[dict[str, str]] = Field(..., description="Array of recipient email addresses")
    with_history: bool = Field(..., description="Include document history")
    client_timestamp: int = Field(..., description="Client timestamp")


class FieldInviteRecipient(BaseModel):
    """Recipient information for field invite."""

    name: str = Field(..., description="Recipient name")
    email: str = Field(..., description="Recipient email")
    phone_invite: str | None = Field(None, description="Phone invite information")
    email_group: dict[str, str | None] = Field(..., description="Email group information")
    order: int = Field(..., description="Signing order")
    attributes: dict[str, Any] = Field(..., description="Recipient attributes")
    documents: list[dict[str, str]] = Field(..., description="Documents assigned to recipient")


class GetRecipientsResponse(BaseModel):
    """Response model for getting document group recipients."""

    data: dict[str, Any] = Field(..., description="Recipients data with recipients, unmapped documents, and CC")


# Freeform Invite models (for document signing)
class FreeformInviteRecipient(BaseModel):
    """Recipient information for freeform invite."""

    email: str = Field(..., description="Recipient's email address")
    redirect_uri: str | None = Field(None, description="Link that opens after signing completion. Overrides the general redirect_uri")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Close' button")
    redirect_target: str | None = Field("blank", description="Redirect target: 'blank' for new tab, 'self' for same tab")
    language: str | None = Field(None, description="Signing session and notification email language: 'en', 'es', 'fr'")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateFreeformInviteRequest(BaseModel):
    """Request model for creating freeform invite."""

    to: list[FreeformInviteRecipient] = Field(..., description="Array with the list of signers")
    cc: list[FreeformInviteRecipient] | None = Field(None, description="Array with the list of CC email addresses")
    message: str | None = Field(None, description="Email body message for all signers")
    subject: str | None = Field(None, description="Email subject for all signers")
    redirect_uri: str | None = Field(None, description="Default redirect URI when document is signed")
    client_timestamp: int = Field(..., description="UNIX timestamp", ge=0, le=4294967295)


class CreateFreeformInviteResponse(BaseModel):
    """Response model for creating freeform invite."""

    data: dict[str, str] = Field(..., description="Response data containing the invite ID")


class CancelFreeformInviteRequest(BaseModel):
    """Request model for canceling freeform invite."""

    reason: str | None = Field(None, description="Cancellation reason", max_length=1000)
    client_timestamp: int = Field(..., description="UNIX timestamp")


# General Embedded Invite models (for document signing)
class EmbeddedInviteAuthentication(BaseModel):
    """Authentication settings for embedded invite signer."""

    type: str = Field(..., description="Authentication type: 'phone' or 'password'")
    password: str | None = Field(None, description="Password for password authentication")
    method: str | None = Field(None, description="Method for phone authentication: 'sms' or 'phone_call'")
    phone: str | None = Field(None, description="Phone number for phone authentication")
    sms_message: str | None = Field(None, description="Custom SMS message with {password} placeholder")


class EmbeddedInviteDocument(BaseModel):
    """Document information for embedded invite signer."""

    id: str = Field(..., description="Document ID")
    role: str | None = Field(None, description="Signer role in the document")
    action: str = Field(..., description="Signer action: 'sign' or 'view'")


class EmbeddedInviteSigner(BaseModel):
    """Signer information for embedded invite."""

    email: str = Field(..., description="Signer's email address")
    auth_method: str = Field(..., description="Authentication method in integrated app: 'password', 'email', 'mfa', 'biometric', 'social', 'other', 'none'")
    first_name: str | None = Field(None, description="Signer's first name")
    last_name: str | None = Field(None, description="Signer's last name")
    language: str | None = Field(None, description="Signing session language: 'en', 'es', 'fr'")
    required_preset_signature_name: str | None = Field(None, description="Prefilled signature name, disabled for editing")
    redirect_uri: str | None = Field(None, description="Link that opens after signing completion")
    decline_redirect_uri: str | None = Field(None, description="Link that opens after signing decline")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Save Progress and Finish Later' or 'Close'")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' for new tab, 'self' for same tab")
    delivery_type: str | None = Field(None, description="Invite delivery method: 'email' or 'link'")
    subject: str | None = Field(None, description="Invite email subject (max 1000 chars)")
    message: str | None = Field(None, description="Invite email message (max 5000 chars)")
    link_expiration: int | None = Field(None, description="Email invite expiration in minutes (15-43200)")
    documents: list[EmbeddedInviteDocument] = Field(..., description="Documents the signer is invited to sign")
    session_expiration: int | None = Field(None, description="Signing session expiration in minutes (15-1440)")
    authentication: EmbeddedInviteAuthentication | None = Field(None, description="Recipient authentication settings")


class EmbeddedInviteStep(BaseModel):
    """Single signing step in embedded invite."""

    order: int = Field(..., description="Signing order step number")
    signers: list[EmbeddedInviteSigner] = Field(..., description="Signers for this step")


class CreateEmbeddedInviteRequest(BaseModel):
    """Request model for creating embedded invite."""

    invites: list[EmbeddedInviteStep] = Field(..., description="Array of invite steps with signing order and signer settings")
    sign_as_merged: bool | None = Field(None, description="Whether to send documents as merged file")


class CreateEmbeddedInviteResponse(BaseModel):
    """Response model for creating embedded invite."""

    id: str = Field(..., description="Invite ID")


class EmbeddedInviteResponse(BaseModel):
    """Full response wrapper for embedded invite creation."""

    data: CreateEmbeddedInviteResponse = Field(..., description="Embedded invite response data")


class GenerateEmbeddedInviteLinkRequest(BaseModel):
    """Request model for generating embedded invite link."""

    email: str = Field(..., description="Signer's email address")
    auth_method: str = Field(
        ...,
        description="Authentication method in integrated app: 'password', 'email', 'mfa', 'social', 'biometric', 'other', 'none'. Must match the value specified when creating the embedded invite",
    )
    link_expiration: int | None = Field(None, description="Link expiration in minutes (15-45)")
    session_expiration: int | None = Field(None, description="Session expiration in minutes (15-1440)")


class GenerateEmbeddedInviteLinkResponse(BaseModel):
    """Response model for generating embedded invite link."""

    link: str = Field(..., description="Embedded signing link")


class EmbeddedInviteLinkResponse(BaseModel):
    """Full response wrapper for embedded invite link generation."""

    data: GenerateEmbeddedInviteLinkResponse = Field(..., description="Embedded invite link response data")


# Document Freeform Invite models (for document signing without fields)
class DocumentFreeformInviteRecipient(BaseModel):
    """Recipient information for document freeform invite."""

    email: str = Field(..., description="Signer's email address")
    redirect_uri: str | None = Field(None, description="Link that opens after signing completion. Overrides the general redirect_uri")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Close' button")
    redirect_target: str | None = Field(None, description="Redirect target: 'blank' for new tab, 'self' for same tab")
    language: str | None = Field(None, description="Signing session and notification email language: 'en', 'es', 'fr'")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class CreateDocumentFreeformInviteRequest(BaseModel):
    """Request model for creating document freeform invite."""

    to: str = Field(..., description="Signer's email address")
    from_: str = Field(..., alias="from", description="Sender's email address. You can use only the email address associated with your SignNow account (login email) as 'from' address")
    cc: list[str] | None = Field(None, description="Email addresses for CC recipients")
    subject: str | None = Field(None, description="Email subject for the signer")
    message: str | None = Field(None, description="Email body message for the signer")
    cc_subject: str | None = Field(None, description="CC email subject for the recipients")
    cc_message: str | None = Field(None, description="CC email body message for the recipients")
    sms_message: str | None = Field(None, description="Custom SMS message")
    language: str | None = Field(
        None,
        description="Sets the language of the signing session and notification emails for the signer. Possible values: 'en' for English, 'es' for Spanish, and 'fr' for French",
    )
    redirect_uri: str | None = Field(None, description="When a document is signed, the signer is redirected to this URI")
    close_redirect_uri: str | None = Field(None, description="The link that opens after a signer selects the 'Close' button")
    redirect_target: str | None = Field(
        None,
        description="Determines whether to open the redirect link in the new tab in the browser, or in the same tab after the signing session. Possible values: 'blank' - opens the link in the new tab, 'self' - opens the link in the same tab",
    )


class CreateDocumentFreeformInviteResponse(BaseModel):
    """Response model for creating document freeform invite."""

    result: str = Field(..., description="Result status")
    id: str = Field(..., description="Invite ID")
    callback_url: str = Field(..., description="Callback URL")


class UploadDocumentRequest(BaseModel):
    """Request model for uploading document."""

    file: bytes = Field(..., description="Document file content as bytes")
    filename: str = Field(..., description="Name of the file to upload")
    check_fields: bool = Field(True, description="Whether to check for fields in the document")


class UploadDocumentResponse(BaseModel):
    """Response model for uploading document."""

    id: str = Field(..., description="ID of the uploaded document")
