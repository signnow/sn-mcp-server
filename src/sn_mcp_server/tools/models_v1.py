"""
Response models for v1.0 backward-compatible tool contracts (signnow_v1.py).

All classes here mirror the v1.0.1 external API surface.
Current (v2) models live in models.py; this file is intentionally separate
so that models.py stays focused on the current contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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
