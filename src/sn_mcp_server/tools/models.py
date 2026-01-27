"""
MCP Tools Data Models

Pydantic models for MCP tools results and responses.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from signnow_client.models.document_groups import DocumentGroupV2FieldInvite
from signnow_client.models.folders_lite import DocumentGroupInviteLite, FieldInviteLite
from signnow_client.models.templates_and_documents import DocumentFieldInviteStatus


# ----------------------------
# Status constants
# ----------------------------


# Unified invite status values
class InviteStatusValues:
    """Constants for unified invite status values."""

    PENDING = "pending"
    CREATED = "created"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

    @staticmethod
    def from_raw_status(raw_status: str | None) -> str:
        """Normalize raw status from API to unified status value.

        Args:
            raw_status: Raw status string from API (e.g., "sent", "fulfilled", "declined")

        Returns:
            Unified status value (pending, created, completed, declined, expired, unknown)
        """
        if not raw_status:
            return InviteStatusValues.UNKNOWN

        normalized = (raw_status or "").strip().lower()

        # Check status sets in priority order
        if normalized in InviteStatusSets.DECLINED:
            return InviteStatusValues.DECLINED
        if normalized in InviteStatusSets.EXPIRED:
            return InviteStatusValues.EXPIRED
        if normalized in InviteStatusSets.DONE:
            return InviteStatusValues.COMPLETED
        if normalized in InviteStatusSets.PENDING:
            return InviteStatusValues.PENDING
        if normalized in InviteStatusSets.CREATED:
            return InviteStatusValues.CREATED

        return InviteStatusValues.UNKNOWN


# Raw status sets for status computation
class InviteStatusSets:
    """Sets of raw status values grouped by meaning."""

    CREATED = {"created", "new"}
    PENDING = {"pending", "sent", "waiting"}
    DONE = {"fulfilled", "signed", "completed", "done"}
    DECLINED = {"declined", "rejected", "canceled", "cancelled"}
    EXPIRED = {"expired"}


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
    invite: SimplifiedInvite | None = Field(None, description="Unified invite info")
    documents: list[DocumentGroupDocument] = Field(..., description="List of documents in this group")


class SimplifiedDocumentGroupDocument(BaseModel):
    """Simplified document information for MCP tools."""

    id: str = Field(..., description="Document ID")
    name: str = Field(..., description="Document name")
    roles: list[str] = Field(..., description="Roles defined for this document")


class SimplifiedInviteParticipant(BaseModel):
    email: str | None = Field(None, description="Participant email")
    role: str | None = Field(None, description="Role (for document field_invites)")
    action: str | None = Field(None, description="Action (for document-group invites)")
    order: int | None = Field(None, description="Signing order if present")

    status: str | None = Field(None, description="Raw participant status from API")
    created: int | None = Field(None, description="Unix created timestamp")
    updated: int | None = Field(None, description="Unix updated timestamp")

    expires_at: int | None = Field(None, description="Unix expiration timestamp")
    expired: bool = Field(False, description="Is this participant expired")

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        """Normalize status string for comparison."""
        return (status or "").strip().lower()

    @staticmethod
    def check_expired(status: str | None, expires_at: int | None, now: int) -> bool:
        """Check if participant is expired based on status and expiration time."""
        st = SimplifiedInviteParticipant._normalize_status(status)
        if st in InviteStatusSets.EXPIRED:
            return True
        if expires_at is None:
            return False
        return (now > expires_at) and (st in InviteStatusSets.PENDING or st == "")

    @classmethod
    def from_field_invite(cls, field_invite: FieldInviteLite, now: int) -> SimplifiedInviteParticipant:
        """Create participant from FieldInviteLite."""
        expires_at = field_invite.expiration_time
        status = field_invite.status
        expired = cls.check_expired(field_invite.status, expires_at, now)

        if expired:
            status = InviteStatusValues.EXPIRED

        return cls(
            email=field_invite.email,
            role=field_invite.role,
            action="sign",
            order=None,
            status=status,
            created=field_invite.created,
            updated=field_invite.updated,
            expires_at=expires_at,
            expired=expired,
        )

    @classmethod
    def from_group_invite(cls, group_invite: DocumentGroupInviteLite, now: int) -> SimplifiedInviteParticipant:
        """Create participant from DocumentGroupInviteLite."""
        expires_at = group_invite.expiration_time

        # is_full_declined upgrades to declined
        status = group_invite.status
        if group_invite.is_full_declined:
            status = InviteStatusValues.DECLINED

        expired = cls.check_expired(status, expires_at, now)

        return cls(
            email=group_invite.email,
            role=None,
            action=group_invite.action,
            order=group_invite.order,
            status=status,
            created=group_invite.created,
            updated=group_invite.updated,
            expires_at=expires_at,
            expired=expired,
        )

    @staticmethod
    def _parse_timestamp(value: str | int | None) -> int | None:
        """Parse timestamp from string or int to int."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        return None

    @classmethod
    def from_document_field_invite(cls, field_invite: DocumentFieldInviteStatus, now: int) -> SimplifiedInviteParticipant:
        """Create participant from DocumentFieldInviteStatus."""
        created = cls._parse_timestamp(field_invite.created)
        updated = cls._parse_timestamp(field_invite.updated)
        # DocumentFieldInviteStatus doesn't have expiration_time, so it's None
        expires_at = None
        status = field_invite.status
        expired = cls.check_expired(status, expires_at, now)

        if expired:
            status = InviteStatusValues.EXPIRED

        return cls(
            email=field_invite.email,
            role=field_invite.role,
            action="sign",
            order=None,
            status=status,
            created=created,
            updated=updated,
            expires_at=expires_at,
            expired=expired,
        )

    @classmethod
    def from_document_group_v2_field_invite(cls, field_invite: DocumentGroupV2FieldInvite, now: int) -> SimplifiedInviteParticipant:
        """Create participant from DocumentGroupV2FieldInvite."""
        expires_at = field_invite.expiration_time
        status = field_invite.status
        expired = cls.check_expired(status, expires_at, now)

        if expired:
            status = InviteStatusValues.EXPIRED

        return cls(
            email=field_invite.signer_email,  # DocumentGroupV2FieldInvite uses signer_email instead of email
            role=None,  # DocumentGroupV2FieldInvite doesn't have role
            action="sign",
            order=None,
            status=status,
            created=field_invite.created,
            updated=field_invite.updated,
            expires_at=expires_at,
            expired=expired,
        )


class SimplifiedInvite(BaseModel):
    invite_id: str | None = Field(None, description="Invite ID if present")
    status: str = Field(
        InviteStatusValues.UNKNOWN,
        description=(
            "Unified invite status. Values: "
            "pending (awaiting actions), created (created but not sent), "
            "completed (all actions done), "
            "declined (someone declined), expired (invite deadline passed), "
            "unknown (status could not be determined)."
        ),
    )
    status_raw: str | None = Field(
        None,
        description=(
            "Raw group-level invite status as returned by SignNow. "
            "Possible values depend on SignNow API (examples seen here: "
            "created, new, sent, pending, waiting, fulfilled, signed, completed, "
            "done, declined, rejected, canceled, cancelled, expired). "
            "created means the document was created but not sent."
        ),
    )

    expires_at: int | None = Field(None, description="Unified invite expiration timestamp")
    expired: bool = Field(False, description="Is invite expired")

    participants: list[SimplifiedInviteParticipant] = Field(default_factory=list)

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        """Normalize status string for comparison."""
        return (status or "").strip().lower()

    @staticmethod
    def pick_expires_at(participants: list["SimplifiedInviteParticipant"]) -> int | None:
        """Pick expiration time from participants (prefer pending, then any minimum)."""
        # 1) nearest deadline among pending (most useful for UI)
        pending_times = [p.expires_at for p in participants if p.expires_at and SimplifiedInvite._normalize_status(p.status) in InviteStatusSets.PENDING]
        if pending_times:
            return min(pending_times)
        # 2) otherwise — any minimum
        all_times = [p.expires_at for p in participants if p.expires_at]
        return min(all_times) if all_times else None

    @staticmethod
    def compute_status(
        participants: list["SimplifiedInviteParticipant"],
        invite_expired: bool,
        raw_status: str | None = None,
    ) -> str:
        """Compute unified invite status from participants and raw status."""
        # 1) explicit statuses with priority
        status_from_raw = InviteStatusValues.from_raw_status(raw_status)
        if status_from_raw != InviteStatusValues.UNKNOWN:
            return status_from_raw

        # 2) derive from participants
        st_list = [SimplifiedInvite._normalize_status(p.status) for p in participants if p.status is not None]

        if any(st in InviteStatusSets.DECLINED for st in st_list):
            return InviteStatusValues.DECLINED
        if invite_expired or any(st in InviteStatusSets.EXPIRED for st in st_list):
            return InviteStatusValues.EXPIRED
        if st_list and all(st in InviteStatusSets.DONE for st in st_list):
            return InviteStatusValues.COMPLETED
        has_pending = any(st in InviteStatusSets.PENDING for st in st_list)
        if has_pending:
            return InviteStatusValues.PENDING
        if any(st in InviteStatusSets.CREATED for st in st_list):
            return InviteStatusValues.CREATED

        return InviteStatusValues.UNKNOWN

    @classmethod
    def from_field_invites(cls, field_invites: list[FieldInviteLite] | None, now: int) -> SimplifiedInvite | None:
        """Create invite from list of FieldInviteLite."""
        if not field_invites:
            return None

        participants: list[SimplifiedInviteParticipant] = []
        for fi in field_invites:
            participants.append(SimplifiedInviteParticipant.from_field_invite(fi, now))

        expires_at = cls.pick_expires_at(participants)
        invite_expired = any(p.expired for p in participants)
        status = cls.compute_status(participants, invite_expired, raw_status=None)

        return cls(
            invite_id=None,
            status=status,
            status_raw=None,
            expires_at=expires_at,
            expired=invite_expired,
            participants=participants,
        )

    @classmethod
    def from_group_invites(
        cls,
        invite_id: str | None,
        raw_status: str | None,
        invites: list[DocumentGroupInviteLite] | None,
        now: int,
    ) -> SimplifiedInvite | None:
        """Create invite from list of DocumentGroupInviteLite."""
        if not invites and not invite_id and not raw_status:
            return None

        participants: list[SimplifiedInviteParticipant] = []
        if invites:
            for inv in invites:
                participants.append(SimplifiedInviteParticipant.from_group_invite(inv, now))

        expires_at = cls.pick_expires_at(participants)
        invite_expired = any(p.expired for p in participants) or (cls._normalize_status(raw_status) in InviteStatusSets.EXPIRED)
        status = cls.compute_status(participants, invite_expired, raw_status=raw_status)

        return cls(
            invite_id=invite_id,
            status=status,
            status_raw=raw_status,
            expires_at=expires_at,
            expired=invite_expired,
            participants=participants,
        )

    @classmethod
    def from_document_field_invites(cls, field_invites: list[DocumentFieldInviteStatus] | None, now: int) -> SimplifiedInvite | None:
        """Create invite from list of DocumentFieldInviteStatus from /document/{id} endpoint."""
        if not field_invites:
            return None

        participants: list[SimplifiedInviteParticipant] = []
        for fi in field_invites:
            participants.append(SimplifiedInviteParticipant.from_document_field_invite(fi, now))

        expires_at = cls.pick_expires_at(participants)
        invite_expired = any(p.expired for p in participants)
        status = cls.compute_status(participants, invite_expired, raw_status=None)

        return cls(
            invite_id=None,
            status=status,
            status_raw=None,
            expires_at=expires_at,
            expired=invite_expired,
            participants=participants,
        )

    @classmethod
    def from_document_group_v2(
        cls,
        invite_id: str | None,
        raw_status: str | None,
        field_invites: list[DocumentGroupV2FieldInvite] | None,
        now: int,
    ) -> SimplifiedInvite | None:
        """Create invite from document group v2 API data."""
        if not field_invites and not invite_id and not raw_status:
            return None

        participants: list[SimplifiedInviteParticipant] = []
        if field_invites:
            for fi in field_invites:
                participants.append(SimplifiedInviteParticipant.from_document_group_v2_field_invite(fi, now))

        expires_at = cls.pick_expires_at(participants)
        invite_expired = any(p.expired for p in participants) or (cls._normalize_status(raw_status) in InviteStatusSets.EXPIRED)
        status = cls.compute_status(participants, invite_expired, raw_status=raw_status)

        return cls(
            invite_id=invite_id,
            status=status,
            status_raw=raw_status,
            expires_at=expires_at,
            expired=invite_expired,
            participants=participants,
        )


class SimplifiedDocumentGroup(BaseModel):
    """Simplified document group for MCP tools."""

    last_updated: int = Field(..., description="Unix timestamp of the last update")
    id: str = Field(..., description="Document group or document ID")
    name: str = Field(..., description="Name of the document group or document")
    entity_type: str = Field(..., description="Type of entity: 'document' or 'document_group'")
    invite: SimplifiedInvite | None = Field(None, description="Unified invite info")
    documents: list[SimplifiedDocumentGroupDocument] = Field(..., description="List of documents in this group")


class SimplifiedDocumentGroupsResponse(BaseModel):
    """Simplified response for MCP tools with document groups"""

    document_groups: list[SimplifiedDocumentGroup]
    document_group_total_count: int = Field(..., description="Total number of document groups")


# Invite sending models
class InviteRecipient(BaseModel):
    """Recipient information for invite."""

    email: str = Field(..., description="Recipient's email address")
    role: str = Field(..., description="Recipient's role name in the document")
    message: str | None = Field(None, description="Custom email message for the recipient")
    subject: str | None = Field(None, description="Custom email subject for the recipient")
    action: str = Field(default="sign", description="Allowed action with a document. Possible values: 'view', 'sign', 'approve'")
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
    role: str = Field(..., description="Recipient's role name in the document")
    action: str = Field(default="sign", description="Allowed action with a document. Possible values: 'view', 'sign', 'approve'")
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
    role: str = Field(..., description="Role name for this action")


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


class SigningLinkResponse(BaseModel):
    """Response model for signing link."""

    link: str = Field(..., description="Signing link for the document or document group")


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
