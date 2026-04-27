"""
Response models for v1.0 backward-compatible tool contracts (signnow_v1.py).

All classes here mirror the v1.0.1 external API surface.
Current (v2) models live in models.py; this file is intentionally separate
so that models.py stays focused on the current contract.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .models import SimplifiedInvite

# ─── v1 input models ─────────────────────────────────────────────────────────
# InviteRecipient v2 added: reminder, expiration_days, authentication.
# v1.0.1 contract did NOT expose these fields; v1 tools use the strict subset.


class InviteRecipientV1(BaseModel):
    """v1.0.1 invite recipient — no reminder/expiration_days/authentication fields."""

    email: str = Field(..., description="Recipient's email address")
    role: str = Field(..., description="Recipient's role name in the document")
    message: str | None = Field(None, description="Custom email message for the recipient")
    subject: str | None = Field(None, description="Custom email subject for the recipient")
    action: str = Field(default="sign", description="Allowed action with a document. Possible values: 'view', 'sign', 'approve'")
    redirect_uri: str | None = Field(None, description="Link that opens after completion")
    redirect_target: str | None = Field("blank", description="Redirect target: 'blank' for new tab, 'self' for same tab")
    decline_redirect_uri: str | None = Field(None, description="URL that opens after decline")
    close_redirect_uri: str | None = Field(None, description="Link that opens when clicking 'Close' button")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Override model_dump to exclude redirect_target if redirect_uri is not provided."""
        data = super().model_dump(**kwargs)
        if (not self.redirect_uri or not self.redirect_uri.strip()) and "redirect_target" in data:
            del data["redirect_target"]
        return data


class InviteOrderV1(BaseModel):
    """v1.0.1 invite order with v1 recipients (no v2-only fields)."""

    order: int = Field(..., description="Order number for this step")
    recipients: list[InviteRecipientV1] = Field(..., description="List of recipients for this order")


# ─── v1 output models — get_document ─────────────────────────────────────────
# v2 widened DocumentField.name from str → str | None.
# v1.0.1 contract guaranteed name: str.


class DocumentFieldV1(BaseModel):
    """v1.0.1 document field — name is always str (never None)."""

    id: str = Field(..., description="Field ID")
    type: str = Field(..., description="Field type")
    role_id: str = Field(..., description="Role ID associated with this field")
    value: str = Field(..., description="Field value")
    name: str = Field(..., description="Field name")


class DocumentGroupDocumentV1(BaseModel):
    """v1.0.1 document in a group — uses DocumentFieldV1."""

    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    roles: list[str] = Field(..., description="Roles defined for this document")
    fields: list[DocumentFieldV1] = Field(default=[], description="Fields defined in this document")


class DocumentGroupV1(BaseModel):
    """v1.0.1 document group response — DocumentField.name guaranteed str."""

    last_updated: int = Field(..., description="Unix timestamp of the last update")
    entity_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    entity_type: str = Field(..., description="Type of entity: 'document' or 'document_group'")
    invite: SimplifiedInvite | None = Field(None, description="Unified invite info")
    documents: list[DocumentGroupDocumentV1] = Field(..., description="List of documents in this group")


# ─── v1 response models — send_invite / create_embedded_* ────────────────────


class SendInviteResponseV1(BaseModel):
    """v1.0 response shape for send_invite: invite_id + invite_entity only."""

    invite_id: str = Field(..., description="ID of the created invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")


class CreateEmbeddedInviteResponseV1(BaseModel):
    """v1.0 response shape for create_embedded_invite."""

    invite_id: str = Field(..., description="ID of the created embedded invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")
    recipient_links: list[dict[str, str]] = Field(..., description="Array of objects with role and link for recipients with delivery_type='link'")


class CreateEmbeddedEditorResponseV1(BaseModel):
    """v1.0 response shape for create_embedded_editor: no created_entity_* fields."""

    editor_entity: str = Field(..., description="Type of editor entity: 'document' or 'document_group'")
    editor_url: str = Field(..., description="URL for the embedded editor")


class CreateEmbeddedSendingResponseV1(BaseModel):
    """v1.0 response shape for create_embedded_sending: no created_entity_* fields."""

    sending_entity: str = Field(..., description="Type of sending entity: 'document', 'document_group', or 'invite'")
    sending_url: str = Field(..., description="URL for the embedded sending")


# ─── Compound template workflow response models ───────────────────────────────
# These tools were removed in v2 (merged into parent tools via expanded entity_type).
# Response models are preserved here for the v1.0 compound tools in signnow_v1.py.


class SendInviteFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and sending invite immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    invite_id: str = Field(..., description="ID of the created invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")


class CreateEmbeddedSendingFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and creating embedded sending immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    sending_entity: str = Field(..., description="Type of sending entity: 'document', 'document_group', or 'invite'")
    sending_url: str = Field(..., description="URL for the embedded sending")


class CreateEmbeddedEditorFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and creating embedded editor immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    editor_entity: str = Field(..., description="Type of editor entity: 'document' or 'document_group'")
    editor_url: str = Field(..., description="URL for the embedded editor")


class CreateEmbeddedInviteFromTemplateResponse(BaseModel):
    """Response model for creating document/group from template and creating embedded invite immediately."""

    created_entity_id: str = Field(..., description="ID of the created document or document group")
    created_entity_type: str = Field(..., description="Type of created entity: 'document' or 'document_group'")
    created_entity_name: str = Field(..., description="Name of the created entity")
    invite_id: str = Field(..., description="ID of the created embedded invite")
    invite_entity: str = Field(..., description="Type of invite entity: 'document' or 'document_group'")
    recipient_links: list[dict[str, str]] = Field(..., description="Array of objects with role and link for recipients with delivery_type='link'")
