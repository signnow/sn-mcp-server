"""Unit tests for cancel_invite module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIHTTPError
from signnow_client.models.document_groups import (
    DocumentGroupV2Data,
    DocumentGroupV2FreeformInvite,
    GetDocumentGroupV2Response,
)
from signnow_client.models.templates_and_documents import (
    DocumentFieldInviteStatus,
    DocumentFreeFormInvite,
    DocumentResponse,
    FieldInviteStatus,
    GetDocumentFreeFormInvitesResponse,
    GetFieldInviteResponse,
)
from sn_mcp_server.tools.cancel_invite import (
    _cancel_invite,
    _resolve_document_group_invite_info,
    _resolve_document_invite_info,
    _resolve_entity_type,
)

TOKEN = "test-token"  # noqa: S105
DOC_ID = "doc-123"
GRP_ID = "grp-456"
INVITE_ID = "inv-789"


# ── helpers ───────────────────────────────────────────────────────────────────


def _field_invite(
    invite_id: str = "inv-1",
    status: str = "pending",
    is_embedded: bool | None = None,
) -> DocumentFieldInviteStatus:
    """Create a minimal DocumentFieldInviteStatus."""
    return DocumentFieldInviteStatus.model_construct(
        id=invite_id,
        status=status,
        email="signer@x.com",
        role="Signer 1",
        role_id="role-abc",
        reminder="0",
        created="1700000000",
        updated="1700000000",
        declined=[],
        is_embedded=is_embedded,
    )


def _doc(field_invites: list[DocumentFieldInviteStatus] | None = None) -> DocumentResponse:
    """Create a minimal DocumentResponse."""
    return DocumentResponse.model_construct(
        id=DOC_ID,
        field_invites=field_invites if field_invites is not None else [],
        template=False,
    )


def _group_data(
    state: str = "pending",
    invite_id: str | None = INVITE_ID,
    freeform_invite: DocumentGroupV2FreeformInvite | None = None,
) -> DocumentGroupV2Data:
    """Create a minimal DocumentGroupV2Data."""
    return DocumentGroupV2Data.model_construct(
        id=GRP_ID,
        name="Test Group",
        created=1700000000,
        state=state,
        invite_id=invite_id,
        freeform_invite=freeform_invite,
        documents=[],
    )


def _group_resp(
    state: str = "pending",
    invite_id: str | None = INVITE_ID,
    freeform_invite: DocumentGroupV2FreeformInvite | None = None,
) -> GetDocumentGroupV2Response:
    """Create a minimal GetDocumentGroupV2Response."""
    return GetDocumentGroupV2Response.model_construct(
        data=_group_data(state=state, invite_id=invite_id, freeform_invite=freeform_invite),
    )


def _field_invite_response(is_embedded: bool = False) -> GetFieldInviteResponse:
    """Create a minimal GetFieldInviteResponse."""
    return GetFieldInviteResponse.model_construct(
        invite=FieldInviteStatus.model_construct(
            id=INVITE_ID,
            status="pending",
            is_embedded=is_embedded,
            steps=[],
        ),
    )


# ── TestResolveDocumentInviteInfo ─────────────────────────────────────────────


class TestResolveDocumentInviteInfo:
    """Tests for _resolve_document_invite_info."""

    def test_pending_field_invite_returns_field_type(self) -> None:
        """Pending field invite → ('field', 'pending', [id])."""
        client = MagicMock()
        doc = _doc([_field_invite("inv-1", "pending")])

        invite_type, status, ids = _resolve_document_invite_info(client, TOKEN, DOC_ID, doc)

        assert invite_type == "field"
        assert status == "pending"
        assert ids == ["inv-1"]
        client.get_document_freeform_invites.assert_not_called()

    def test_embedded_field_invite_returns_embedded_type(self) -> None:
        """Field invite with is_embedded=True → ('embedded', 'pending', [id])."""
        client = MagicMock()
        doc = _doc([_field_invite("inv-1", "pending", is_embedded=True)])

        invite_type, status, ids = _resolve_document_invite_info(client, TOKEN, DOC_ID, doc)

        assert invite_type == "embedded"
        assert status == "pending"
        assert ids == ["inv-1"]

    def test_all_fulfilled_returns_completed(self) -> None:
        """All field invites fulfilled → (None, 'completed', [])."""
        client = MagicMock()
        doc = _doc([_field_invite("inv-1", "fulfilled")])

        invite_type, status, ids = _resolve_document_invite_info(client, TOKEN, DOC_ID, doc)

        assert status == "completed"
        assert ids == []
        assert invite_type is None

    def test_freeform_invite_pending(self) -> None:
        """No field invites, freeform pending → ('freeform', 'pending', [id])."""
        client = MagicMock()
        freeform = DocumentFreeFormInvite.model_construct(id="ff-1", status="pending", created=1700000000, email="x@y.com")
        client.get_document_freeform_invites.return_value = GetDocumentFreeFormInvitesResponse.model_construct(data=[freeform])
        doc = _doc([])  # empty field_invites triggers freeform path

        invite_type, status, ids = _resolve_document_invite_info(client, TOKEN, DOC_ID, doc)

        assert invite_type == "freeform"
        assert status == "pending"
        assert ids == ["ff-1"]
        client.get_document_freeform_invites.assert_called_once_with(TOKEN, DOC_ID)

    def test_no_invites_returns_no_invite(self) -> None:
        """No field invites, no freeform → (None, 'no_invite', [])."""
        client = MagicMock()
        client.get_document_freeform_invites.return_value = GetDocumentFreeFormInvitesResponse.model_construct(data=[])
        doc = _doc([])

        invite_type, status, ids = _resolve_document_invite_info(client, TOKEN, DOC_ID, doc)

        assert status == "no_invite"
        assert ids == []
        assert invite_type is None

    def test_mixed_pending_and_fulfilled(self) -> None:
        """Some pending, some fulfilled → ('field', 'pending', [pending_ids])."""
        client = MagicMock()
        doc = _doc([_field_invite("inv-1", "pending"), _field_invite("inv-2", "fulfilled")])

        invite_type, status, ids = _resolve_document_invite_info(client, TOKEN, DOC_ID, doc)

        assert invite_type == "field"
        assert status == "pending"
        assert ids == ["inv-1"]


# ── TestResolveDocumentGroupInviteInfo ────────────────────────────────────────


class TestResolveDocumentGroupInviteInfo:
    """Tests for _resolve_document_group_invite_info."""

    def test_pending_field_invite_not_embedded(self) -> None:
        """State=pending with invite_id, not embedded → ('field', 'pending', [invite_id])."""
        client = MagicMock()
        client.get_field_invite.return_value = _field_invite_response(is_embedded=False)
        gdata = _group_data(state="pending", invite_id=INVITE_ID)

        invite_type, status, ids = _resolve_document_group_invite_info(client, TOKEN, GRP_ID, gdata)

        assert invite_type == "field"
        assert status == "pending"
        assert ids == [INVITE_ID]
        client.get_field_invite.assert_called_once_with(TOKEN, GRP_ID, INVITE_ID)

    def test_pending_embedded_invite(self) -> None:
        """State=pending with invite_id, is_embedded=True → ('embedded', 'pending', [invite_id])."""
        client = MagicMock()
        client.get_field_invite.return_value = _field_invite_response(is_embedded=True)
        gdata = _group_data(state="pending", invite_id=INVITE_ID)

        invite_type, status, ids = _resolve_document_group_invite_info(client, TOKEN, GRP_ID, gdata)

        assert invite_type == "embedded"
        assert status == "pending"

    def test_pending_freeform_invite(self) -> None:
        """State=pending with no invite_id, freeform_invite set → ('freeform', 'pending', [freeform_id])."""
        client = MagicMock()
        freeform = DocumentGroupV2FreeformInvite.model_construct(id="ff-1", last_id=None)
        gdata = _group_data(state="pending", invite_id=None, freeform_invite=freeform)

        invite_type, status, ids = _resolve_document_group_invite_info(client, TOKEN, GRP_ID, gdata)

        assert invite_type == "freeform"
        assert status == "pending"
        assert ids == ["ff-1"]
        client.get_field_invite.assert_not_called()

    def test_fulfilled_state_returns_completed(self) -> None:
        """State=fulfilled → (None, 'completed', [])."""
        client = MagicMock()
        gdata = _group_data(state="fulfilled")

        invite_type, status, ids = _resolve_document_group_invite_info(client, TOKEN, GRP_ID, gdata)

        assert status == "completed"
        assert invite_type is None
        assert ids == []

    def test_created_state_returns_no_invite(self) -> None:
        """State=created → (None, 'no_invite', [])."""
        client = MagicMock()
        gdata = _group_data(state="created", invite_id=None)

        invite_type, status, ids = _resolve_document_group_invite_info(client, TOKEN, GRP_ID, gdata)

        assert status == "no_invite"

    def test_declined_state_returns_no_invite(self) -> None:
        """State=declined → (None, 'no_invite', [])."""
        client = MagicMock()
        gdata = _group_data(state="declined")

        invite_type, status, ids = _resolve_document_group_invite_info(client, TOKEN, GRP_ID, gdata)

        assert status == "no_invite"


# ── TestResolveEntityType ─────────────────────────────────────────────────────


class TestResolveEntityType:
    """Tests for _resolve_entity_type."""

    def test_explicit_document_type(self) -> None:
        """entity_type='document' → fetches document, skips group call."""
        doc = _doc()
        client = MagicMock()
        client.get_document.return_value = doc

        resolved, entity = _resolve_entity_type(client, TOKEN, DOC_ID, "document")

        assert resolved == "document"
        assert entity is doc
        client.get_document_group_v2.assert_not_called()

    def test_explicit_document_group_type(self) -> None:
        """entity_type='document_group' → fetches group, skips document call."""
        group = _group_resp()
        client = MagicMock()
        client.get_document_group_v2.return_value = group

        resolved, entity = _resolve_entity_type(client, TOKEN, GRP_ID, "document_group")

        assert resolved == "document_group"
        assert entity is group
        client.get_document.assert_not_called()

    def test_auto_detect_prefers_document_group(self) -> None:
        """entity_type=None → tries document_group first."""
        group = _group_resp()
        client = MagicMock()
        client.get_document_group_v2.return_value = group

        resolved, entity = _resolve_entity_type(client, TOKEN, GRP_ID, None)

        assert resolved == "document_group"
        client.get_document.assert_not_called()

    def test_auto_detect_falls_back_to_document_on_404(self) -> None:
        """entity_type=None, group 404 → falls back to document."""
        doc = _doc()
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIHTTPError("not found", 404)
        client.get_document.return_value = doc

        resolved, entity = _resolve_entity_type(client, TOKEN, DOC_ID, None)

        assert resolved == "document"
        assert entity is doc

    def test_invalid_entity_type_raises_value_error(self) -> None:
        """Unsupported entity_type string → ValueError."""
        client = MagicMock()

        with pytest.raises(ValueError, match="Invalid entity_type"):
            _resolve_entity_type(client, TOKEN, DOC_ID, "template")  # type: ignore[arg-type]


# ── TestCancelInvite ──────────────────────────────────────────────────────────


class TestCancelInvite:
    """Tests for _cancel_invite business logic."""

    def _doc_client(self, doc: DocumentResponse) -> MagicMock:
        """Mock client that returns a document on get_document."""
        client = MagicMock()
        client.get_document.return_value = doc
        client.get_document_group_v2.side_effect = Exception("not a group")
        return client

    def _group_client(self, group: GetDocumentGroupV2Response) -> MagicMock:
        """Mock client that returns a document group on get_document_group_v2."""
        client = MagicMock()
        client.get_document_group_v2.return_value = group
        return client

    def test_document_field_invite_cancelled(self) -> None:
        """Document with pending field invite → cancelled, cancel_document_field_invite called."""
        doc = _doc([_field_invite("inv-1", "pending")])
        client = self._doc_client(doc)

        result = _cancel_invite(DOC_ID, "document", None, TOKEN, client)

        assert result.status == "cancelled"
        assert result.entity_type == "document"
        assert result.cancelled_invite_type == "field"
        client.cancel_document_field_invite.assert_called_once()

    def test_document_field_invite_reason_forwarded(self) -> None:
        """Cancellation reason is forwarded to the API call."""
        doc = _doc([_field_invite("inv-1", "pending")])
        client = self._doc_client(doc)

        _cancel_invite(DOC_ID, "document", "Out of office", TOKEN, client)

        call_args = client.cancel_document_field_invite.call_args
        request_obj = call_args[0][2]
        assert request_obj.reason == "Out of office"

    def test_document_embedded_invite_cancelled(self) -> None:
        """Document with embedded invite → cancelled, delete_document_embedded_invites called."""
        doc = _doc([_field_invite("inv-1", "pending", is_embedded=True)])
        client = self._doc_client(doc)

        result = _cancel_invite(DOC_ID, "document", None, TOKEN, client)

        assert result.status == "cancelled"
        assert result.cancelled_invite_type == "embedded"
        client.delete_document_embedded_invites.assert_called_once_with(TOKEN, DOC_ID)
        client.cancel_document_field_invite.assert_not_called()

    def test_document_freeform_invite_cancelled(self) -> None:
        """Document with freeform invite → cancelled, cancel_document_freeform_invite called."""
        freeform = DocumentFreeFormInvite.model_construct(id="ff-1", status="pending", created=1700000000, email="x@y.com")
        client = MagicMock()
        client.get_document.return_value = _doc([])  # empty → freeform path
        client.get_document_group_v2.side_effect = Exception("not a group")
        client.get_document_freeform_invites.return_value = GetDocumentFreeFormInvitesResponse.model_construct(data=[freeform])

        result = _cancel_invite(DOC_ID, "document", None, TOKEN, client)

        assert result.status == "cancelled"
        assert result.cancelled_invite_type == "freeform"
        client.cancel_document_freeform_invite.assert_called_once()

    def test_document_completed_returns_completed(self) -> None:
        """All field invites fulfilled → status='completed', no cancel calls."""
        doc = _doc([_field_invite("inv-1", "fulfilled")])
        client = self._doc_client(doc)

        result = _cancel_invite(DOC_ID, "document", None, TOKEN, client)

        assert result.status == "completed"
        assert result.cancelled_invite_ids == []
        client.cancel_document_field_invite.assert_not_called()

    def test_document_no_invite_returns_invite_not_sent(self) -> None:
        """No field or freeform invites → status='invite_not_sent'."""
        client = MagicMock()
        client.get_document.return_value = _doc([])
        client.get_document_group_v2.side_effect = Exception("not a group")
        client.get_document_freeform_invites.return_value = GetDocumentFreeFormInvitesResponse.model_construct(data=[])

        result = _cancel_invite(DOC_ID, "document", None, TOKEN, client)

        assert result.status == "invite_not_sent"
        client.cancel_document_field_invite.assert_not_called()

    def test_document_group_field_invite_cancelled(self) -> None:
        """Document group with pending field invite → cancel_document_group_field_invite called."""
        group = _group_resp(state="pending", invite_id=INVITE_ID)
        client = self._group_client(group)
        client.get_field_invite.return_value = _field_invite_response(is_embedded=False)

        result = _cancel_invite(GRP_ID, "document_group", None, TOKEN, client)

        assert result.status == "cancelled"
        assert result.entity_type == "document_group"
        assert result.cancelled_invite_type == "field"
        client.cancel_document_group_field_invite.assert_called_once_with(TOKEN, GRP_ID, INVITE_ID)

    def test_document_group_embedded_invite_cancelled(self) -> None:
        """Document group with embedded invite → delete_document_group_embedded_invites called."""
        group = _group_resp(state="pending", invite_id=INVITE_ID)
        client = self._group_client(group)
        client.get_field_invite.return_value = _field_invite_response(is_embedded=True)

        result = _cancel_invite(GRP_ID, "document_group", None, TOKEN, client)

        assert result.status == "cancelled"
        assert result.cancelled_invite_type == "embedded"
        client.delete_document_group_embedded_invites.assert_called_once_with(TOKEN, GRP_ID)
        client.cancel_document_group_field_invite.assert_not_called()

    def test_document_group_freeform_invite_cancelled(self) -> None:
        """Document group with freeform invite → cancel_freeform_invite called."""
        freeform = DocumentGroupV2FreeformInvite.model_construct(id="ff-1", last_id=None)
        group = _group_resp(state="pending", invite_id=None, freeform_invite=freeform)
        client = self._group_client(group)

        result = _cancel_invite(GRP_ID, "document_group", None, TOKEN, client)

        assert result.status == "cancelled"
        assert result.cancelled_invite_type == "freeform"
        client.cancel_freeform_invite.assert_called_once()

    def test_document_group_completed_returns_completed(self) -> None:
        """Document group fulfilled → status='completed'."""
        group = _group_resp(state="fulfilled")
        client = self._group_client(group)

        result = _cancel_invite(GRP_ID, "document_group", None, TOKEN, client)

        assert result.status == "completed"
        client.cancel_document_group_field_invite.assert_not_called()

    def test_document_group_no_invite_returns_invite_not_sent(self) -> None:
        """Document group with no invite → status='invite_not_sent'."""
        group = _group_resp(state="created", invite_id=None)
        client = self._group_client(group)

        result = _cancel_invite(GRP_ID, "document_group", None, TOKEN, client)

        assert result.status == "invite_not_sent"

    def test_auto_detection_prefers_document_group(self) -> None:
        """entity_type=None → tries document_group first, not document."""
        group = _group_resp(state="pending", invite_id=INVITE_ID)
        client = MagicMock()
        client.get_document_group_v2.return_value = group
        client.get_field_invite.return_value = _field_invite_response(is_embedded=False)

        result = _cancel_invite(GRP_ID, None, None, TOKEN, client)

        client.get_document_group_v2.assert_called_once_with(TOKEN, GRP_ID)
        client.get_document.assert_not_called()
        assert result.entity_type == "document_group"

    def test_auto_detection_falls_back_to_document(self) -> None:
        """entity_type=None, group not found → falls back to document."""
        doc = _doc([_field_invite("inv-1", "pending")])
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIHTTPError("not found", 404)
        client.get_document.return_value = doc

        result = _cancel_invite(DOC_ID, None, None, TOKEN, client)

        assert result.entity_type == "document"
        assert result.status == "cancelled"
