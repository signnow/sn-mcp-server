"""
Response models for v3.0 tool contracts (signnow_v3.py).

Standalone per-version models, mirroring models_v1.py. Current (v2) models live
in models.py; this file is intentionally separate so models.py stays focused on
the frozen v2 contract. v3 reuses the unchanged v2 member model
(DocumentGroupDocument) — folder info is exposed at the ENTITY level only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import DocumentGroupDocument, SimplifiedInvite


class DocumentGroupV3(BaseModel):
    """v3.0 document/group response — all frozen v2 DocumentGroup fields plus
    entity-level folder info.

    Members reuse the unchanged v2 ``DocumentGroupDocument`` (no per-member folder
    fields): the folder is an entity-level property in v3.
    """

    last_updated: int = Field(..., description="Unix timestamp of the last update")
    entity_id: str = Field(..., description="Document group ID")
    group_name: str = Field(..., description="Name of the document group")
    entity_type: str = Field(..., description="Type of entity: 'document', 'document_group' or 'template_group'")
    folder_id: str | None = Field(None, description="ID of the folder this entity is stored in, if any")
    folder_name: str | None = Field(None, description="Name of the folder this entity is stored in, if it could be resolved")
    invite: SimplifiedInvite | None = Field(None, description="Unified invite info")
    freeform_invite_id: str | None = Field(None, description="Freeform invite ID, if a freeform invite exists on this entity")
    documents: list[DocumentGroupDocument] = Field(..., description="List of documents in this group")
