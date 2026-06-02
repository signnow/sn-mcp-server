"""
Unit tests for reminder.py — send_invite_reminder business logic.

Mocks SignNowAPIClient with MagicMock; ctx with AsyncMock.
All sync client methods (get_document, get_document_group_v2, resend_field_invite,
resend_document_group_invites) return/raise values set in each test.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import (
    DocumentGroupV2Data,
    DocumentGroupV2Document,
    DocumentGroupV2FieldInvite,
    GetDocumentGroupV2Response,
    ResendDocumentGroupInvitesRequest,
)
from signnow_client.models.templates_and_documents import DocumentFieldInviteStatus, DocumentResponse
from sn_mcp_server.tools.reminder import _send_invite_reminder

# ---------------------------------------------------------------------------
# Factory helpers — model_construct() skips field validation so tests only
# populate the fields that reminder.py actually reads at runtime.
# ---------------------------------------------------------------------------

TOKEN = "unit-test-token"  # noqa: S105
DOC_ID = "doc-abc"
GRP_ID = "grp-xyz"
GRP_INVITE_ID = "ginv-1"


def _doc_fi(email: str, status: str = "pending", fi_id: str | None = None) -> DocumentFieldInviteStatus:
    """Minimal DocumentFieldInviteStatus for reminder.py (reads .id, .email, .status)."""
    return DocumentFieldInviteStatus.model_construct(id=fi_id or f"fi-{email}", email=email, status=status)


def _doc_resp(*field_invites: DocumentFieldInviteStatus) -> DocumentResponse:
    """Minimal DocumentResponse for reminder.py (reads .field_invites)."""
    return DocumentResponse.model_construct(field_invites=list(field_invites))


def _grp_fi(signer_email: str, status: str = "pending") -> DocumentGroupV2FieldInvite:
    """Minimal DocumentGroupV2FieldInvite for reminder.py (reads .signer_email and .status)."""
    return DocumentGroupV2FieldInvite.model_construct(signer_email=signer_email, status=status)


def _grp_doc(doc_id: str, *field_invites: DocumentGroupV2FieldInvite) -> DocumentGroupV2Document:
    """Minimal DocumentGroupV2Document for reminder.py (reads .id and .field_invites)."""
    return DocumentGroupV2Document.model_construct(id=doc_id, field_invites=list(field_invites))


def _grp_resp(*documents: DocumentGroupV2Document, invite_id: str | None = GRP_INVITE_ID) -> GetDocumentGroupV2Response:
    """Minimal GetDocumentGroupV2Response for reminder.py (reads .data.documents and .data.invite_id)."""
    data = DocumentGroupV2Data.model_construct(documents=list(documents), invite_id=invite_id)
    return GetDocumentGroupV2Response.model_construct(data=data)


# ---------------------------------------------------------------------------
# Tests: single document path
# ---------------------------------------------------------------------------


class TestRemindDocument:
    """Tests for _remind_document logic via _send_invite_reminder(entity_type='document')."""

    def _client(self, doc_resp: DocumentResponse, send_side_effect: Exception | None = None) -> MagicMock:
        client = MagicMock()
        client.get_document.return_value = doc_resp
        if send_side_effect is not None:
            client.resend_field_invite.side_effect = send_side_effect
        return client

    async def test_one_pending_recipient_reminded(self) -> None:
        """Single pending field_invite → reminded=[email], skipped=[], failed=[]."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending"))
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "alice@x.com"
        assert result.skipped == []
        assert result.failed == []
        assert result.entity_type == "document"
        assert result.entity_id == DOC_ID

    async def test_resend_called_per_pending_invite_with_field_invite_id(self) -> None:
        """7 pending invites → resend_field_invite called once each, with the field invite id."""
        invites = [(f"fi-{i}", f"user{i}@x.com") for i in range(7)]
        doc = _doc_resp(*[_doc_fi(email, "pending", fi_id) for fi_id, email in invites])
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert len(result.recipients_reminded) == 7
        assert client.resend_field_invite.call_count == 7
        # Each call resends a specific field invite id (2nd positional arg).
        called_ids = {c.args[1] for c in client.resend_field_invite.call_args_list}
        assert called_ids == {fi_id for fi_id, _ in invites}

    async def test_resend_payload_carries_client_timestamp(self) -> None:
        """resend_field_invite gets a ResendFieldInviteRequest with an int client_timestamp."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-A"))
        client = self._client(doc)

        await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        request_data = client.resend_field_invite.call_args.args[2]
        assert isinstance(request_data.client_timestamp, int)

    async def test_mix_pending_and_completed(self) -> None:
        """2 pending + 1 fulfilled → reminded=2, skipped=1."""
        doc = _doc_resp(
            _doc_fi("p1@x.com", "pending"),
            _doc_fi("p2@x.com", "created"),
            _doc_fi("done@x.com", "fulfilled"),
        )
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        reminded_emails = {r.email for r in result.recipients_reminded}
        assert "p1@x.com" in reminded_emails
        assert "p2@x.com" in reminded_emails
        assert len(result.skipped) == 1
        assert result.skipped[0].email == "done@x.com"

    async def test_all_completed_returns_all_skipped(self) -> None:
        """All fulfilled invites → reminded=[], skipped=all, no API send call."""
        doc = _doc_resp(
            _doc_fi("a@x.com", "fulfilled"),
            _doc_fi("b@x.com", "signed"),
        )
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.skipped) == 2
        client.resend_field_invite.assert_not_called()

    async def test_email_filter_match_only_filtered_reminded(self) -> None:
        """email='bob@x.com' filter → only bob is reminded, alice is silently dropped."""
        doc = _doc_resp(
            _doc_fi("alice@x.com", "pending"),
            _doc_fi("bob@x.com", "pending"),
        )
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", "bob@x.com", None, None)

        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "bob@x.com"
        assert client.resend_field_invite.call_count == 1

    async def test_email_filter_no_pending_match_adds_skipped_entry(self) -> None:
        """email filter finds no pending invite → skipped entry with email in reason."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending"))
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", "bob@x.com", None, None)

        assert result.recipients_reminded == []
        assert len(result.skipped) == 1
        assert "bob@x.com" in (result.skipped[0].reason or "")

    async def test_email_filter_matches_completed_signer_single_skipped_entry(self) -> None:
        """BUG-1: email filter matches a fulfilled signer → exactly ONE skipped entry (no duplicate)."""
        doc = _doc_resp(_doc_fi("bob@x.com", "fulfilled"))
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", "bob@x.com", None, None)

        assert result.recipients_reminded == []
        assert len(result.skipped) == 1, f"Expected exactly 1 skipped entry, got {len(result.skipped)}: {result.skipped}"
        assert result.skipped[0].email == "bob@x.com"

    async def test_api_failure_categorised_as_failed(self) -> None:
        """resend_field_invite raises SignNowAPIError → result.failed populated."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending"))
        err = SignNowAPIError("gateway error", status_code=502)
        client = self._client(doc, send_side_effect=err)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.failed) == 1
        assert result.failed[0].email == "alice@x.com"
        assert DOC_ID in (result.failed[0].reason or "")

    async def test_partial_failure_splits_reminded_and_failed(self) -> None:
        """Mixed resend outcomes → first reminded, second failed; loop does not abort early."""
        doc = _doc_resp(
            _doc_fi("ok@x.com", "pending", "fi-ok"),
            _doc_fi("bad@x.com", "pending", "fi-bad"),
        )
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = [None, SignNowAPIError("boom", status_code=502)]

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["ok@x.com"]
        assert [r.email for r in result.failed] == ["bad@x.com"]
        assert DOC_ID in (result.failed[0].reason or "")

    async def test_same_email_pending_and_completed_not_in_skipped(self) -> None:
        """Same address on a pending and a fulfilled invite → reminded only, never in skipped."""
        doc = _doc_resp(
            _doc_fi("alice@x.com", "pending", "fi-1"),
            _doc_fi("alice@x.com", "fulfilled", "fi-2"),
        )
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        assert all(s.email != "alice@x.com" for s in result.skipped), f"alice wrongly in skipped: {result.skipped}"
        assert client.resend_field_invite.call_count == 1


# ---------------------------------------------------------------------------
# Tests: document_group path
# ---------------------------------------------------------------------------


class TestRemindDocumentGroup:
    """Tests for _remind_document_group logic via _send_invite_reminder(entity_type='document_group')."""

    def _client(self, grp_resp: GetDocumentGroupV2Response, send_side_effect: Exception | None = None) -> MagicMock:
        client = MagicMock()
        client.get_document_group_v2.return_value = grp_resp
        if send_side_effect is not None:
            client.resend_document_group_invites.side_effect = send_side_effect
        return client

    async def test_pending_signers_across_docs_all_reminded(self) -> None:
        """Pending signers across multiple docs → resend called once per signer with group + invite id."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("signer1@x.com", "pending")),
            _grp_doc("doc2", _grp_fi("signer2@x.com", "pending")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        reminded_emails = {r.email for r in result.recipients_reminded}
        assert "signer1@x.com" in reminded_emails
        assert "signer2@x.com" in reminded_emails
        assert result.entity_type == "document_group"
        # resend_document_group_invites called once per pending signer with (token, group_id, invite_id, request).
        assert client.resend_document_group_invites.call_count == 2
        for call in client.resend_document_group_invites.call_args_list:
            assert call.args[1] == GRP_ID
            assert call.args[2] == GRP_INVITE_ID

    async def test_missing_group_invite_id_marks_pending_as_failed(self) -> None:
        """No active group invite (data.invite_id is None) → pending signers reported as failed, no send call."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("signer1@x.com", "pending")),
            invite_id=None,
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.failed) == 1
        assert result.failed[0].email == "signer1@x.com"
        client.resend_document_group_invites.assert_not_called()

    async def test_mixed_pending_and_fulfilled_across_docs(self) -> None:
        """Pending on doc1, fulfilled on doc2 → only pending reminded, fulfilled skipped."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("signer1@x.com", "pending")),
            _grp_doc("doc2", _grp_fi("signer2@x.com", "fulfilled")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "signer1@x.com"
        assert len(result.skipped) == 1
        assert result.skipped[0].email == "signer2@x.com"

    async def test_no_pending_docs_all_signers_skipped(self) -> None:
        """All invites fulfilled → no send call, all signers in skipped."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("done@x.com", "fulfilled")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.skipped) >= 1
        skipped_emails = {r.email for r in result.skipped}
        assert "done@x.com" in skipped_emails
        client.resend_document_group_invites.assert_not_called()

    async def test_email_filter_sends_only_matched_signer(self) -> None:
        """email='bob@x.com' → only bob reminded via resend."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("bob@x.com", "pending")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", "bob@x.com", None, None)

        reminded_emails = {r.email for r in result.recipients_reminded}
        assert "bob@x.com" in reminded_emails
        assert "alice@x.com" not in reminded_emails
        assert client.resend_document_group_invites.call_count == 1

    async def test_email_filter_no_match_adds_skipped_with_reason(self) -> None:
        """email filter finds no signer → skipped entry contains the unmatched email."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", "unknown@x.com", None, None)

        assert result.recipients_reminded == []
        assert any("unknown@x.com" in (r.reason or "") for r in result.skipped)

    async def test_mixed_pending_and_fulfilled_on_same_doc(self) -> None:
        """Same doc has pending + fulfilled → pending reminded, fulfilled skipped."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("carol@x.com", "fulfilled")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "alice@x.com"
        skipped_emails = {r.email for r in result.skipped}
        assert "carol@x.com" in skipped_emails, f"carol@x.com missing from skipped: {result.skipped}"

    async def test_email_filter_no_match_pending_signers_not_in_skipped(self) -> None:
        """email filter matches nobody → only the unknown email in skipped, not pending signers."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", "unknown@x.com", None, None)

        skipped_emails = {r.email for r in result.skipped}
        assert "alice@x.com" not in skipped_emails, f"Pending signer alice@x.com wrongly in skipped: {result.skipped}"
        assert any("unknown@x.com" in (r.reason or "") for r in result.skipped)

    async def test_api_failure_categorised_as_failed(self) -> None:
        """resend_document_group_invites raises SignNowAPIError → result.failed populated."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending")),
        )
        err = SignNowAPIError("gateway error", status_code=502)
        client = self._client(grp, send_side_effect=err)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.failed) == 1
        assert result.failed[0].email == "alice@x.com"
        assert GRP_ID in (result.failed[0].reason or "")

    async def test_resend_request_payload_structure(self) -> None:
        """Verify resend_document_group_invites called with a ResendDocumentGroupInvitesRequest per signer."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("bob@x.com", "pending")),
        )
        client = self._client(grp)

        await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        payloads = [c.args[3] for c in client.resend_document_group_invites.call_args_list]
        assert all(isinstance(p, ResendDocumentGroupInvitesRequest) for p in payloads)
        assert {p.email for p in payloads} == {"alice@x.com", "bob@x.com"}
        assert all(isinstance(p.client_timestamp, int) for p in payloads)

    async def test_same_signer_pending_in_multiple_docs_deduped(self) -> None:
        """Same signer pending across two docs → exactly one resend, one reminded entry."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("repeat@x.com", "pending")),
            _grp_doc("doc2", _grp_fi("repeat@x.com", "pending")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert client.resend_document_group_invites.call_count == 1
        assert [r.email for r in result.recipients_reminded] == ["repeat@x.com"]

    async def test_same_signer_pending_and_completed_across_docs_not_skipped(self) -> None:
        """Signer pending on doc1 but fulfilled on doc2 → reminded once, never in skipped (no double-bucket)."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending")),
            _grp_doc("doc2", _grp_fi("alice@x.com", "fulfilled")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        assert all(s.email != "alice@x.com" for s in result.skipped), f"alice wrongly in skipped: {result.skipped}"
        assert client.resend_document_group_invites.call_count == 1

    async def test_partial_failure_splits_reminded_and_failed(self) -> None:
        """Mixed resend outcomes across signers → first reminded, second failed; loop continues."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("ok@x.com", "pending"), _grp_fi("bad@x.com", "pending")),
        )
        client = MagicMock()
        client.get_document_group_v2.return_value = grp
        client.resend_document_group_invites.side_effect = [None, SignNowAPIError("boom", status_code=502)]

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["ok@x.com"]
        assert [r.email for r in result.failed] == ["bad@x.com"]
        assert GRP_ID in (result.failed[0].reason or "")


# ---------------------------------------------------------------------------
# Tests: auto-detection (entity_type=None)
# ---------------------------------------------------------------------------


class TestAutoDetect:
    """Tests for entity_type=None auto-detection: group tried first, document as fallback."""

    async def test_group_detected_first_document_not_called(self) -> None:
        """Group resolution succeeds → entity_type='document_group', get_document never called."""
        grp = _grp_resp(_grp_doc("doc1", _grp_fi("s@x.com", "pending")))
        client = MagicMock()
        client.get_document_group_v2.return_value = grp

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, None, None, None, None)

        assert result.entity_type == "document_group"
        client.get_document.assert_not_called()

    async def test_document_fallback_when_group_404(self) -> None:
        """Group→404, document→success → entity_type='document', both endpoints called."""
        doc = _doc_resp(_doc_fi("s@x.com", "pending"))
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIError("Not found", status_code=404)
        client.get_document.return_value = doc

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, None, None, None, None)

        assert result.entity_type == "document"
        client.get_document_group_v2.assert_called_once_with(TOKEN, DOC_ID)
        client.get_document.assert_called_once_with(TOKEN, DOC_ID)

    async def test_both_404_raises_value_error_with_entity_id(self) -> None:
        """Group→404 and document→404 → ValueError referencing entity_id."""
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIError("Not found", status_code=404)
        client.get_document.side_effect = SignNowAPIError("Not found", status_code=404)

        with pytest.raises(ValueError, match=DOC_ID):
            await _send_invite_reminder(client, TOKEN, DOC_ID, None, None, None, None)

    async def test_non_404_group_error_propagates_immediately(self) -> None:
        """Group→403 → SignNowAPIError re-raised, get_document never called."""
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIError("Forbidden", status_code=403)

        with pytest.raises(SignNowAPIError) as exc_info:
            await _send_invite_reminder(client, TOKEN, GRP_ID, None, None, None, None)

        assert exc_info.value.status_code == 403
        client.get_document.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Tests for entity_type validation before any API call."""

    async def test_invalid_entity_type_raises_value_error(self) -> None:
        """entity_type not in {document, document_group, None} → ValueError immediately."""
        client = MagicMock()

        with pytest.raises(ValueError, match="Invalid entity_type"):
            await _send_invite_reminder(client, TOKEN, DOC_ID, "invoice", None, None, None)

        client.get_document.assert_not_called()
        client.get_document_group_v2.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: progress reporting
# ---------------------------------------------------------------------------


class TestProgressReporting:
    """Tests for ctx.report_progress calls during per-invite resends."""

    async def test_progress_reported_once_per_field_invite(self) -> None:
        """7 pending invites → ctx.report_progress called 7 times with total=7."""
        doc = _doc_resp(*[_doc_fi(f"user{i}@x.com", "pending") for i in range(7)])
        client = MagicMock()
        client.get_document.return_value = doc

        ctx = AsyncMock()

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        assert len(result.recipients_reminded) == 7
        assert ctx.report_progress.call_count == 7
        for progress_call in ctx.report_progress.call_args_list:
            assert progress_call.kwargs["total"] == 7

    async def test_single_pending_reports_once(self) -> None:
        """1 pending invite → ctx.report_progress called exactly once."""
        doc = _doc_resp(_doc_fi("only@x.com", "pending"))
        client = MagicMock()
        client.get_document.return_value = doc

        ctx = AsyncMock()

        await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        assert ctx.report_progress.call_count == 1
        assert ctx.report_progress.call_args.kwargs["total"] == 1

    async def test_no_pending_no_progress_calls(self) -> None:
        """No pending invites → no resend calls → ctx.report_progress never called."""
        doc = _doc_resp(_doc_fi("done@x.com", "fulfilled"))
        client = MagicMock()
        client.get_document.return_value = doc

        ctx = AsyncMock()

        await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        ctx.report_progress.assert_not_called()

    async def test_group_resend_reports_progress_per_signer(self) -> None:
        """Document group with 2 pending signers → ctx.report_progress called twice (one per resend)."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("bob@x.com", "pending")),
        )
        client = MagicMock()
        client.get_document_group_v2.return_value = grp

        ctx = AsyncMock()

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None, ctx=ctx)

        assert len(result.recipients_reminded) == 2
        assert ctx.report_progress.call_count == 2
        for progress_call in ctx.report_progress.call_args_list:
            assert progress_call.kwargs["total"] == 2

    async def test_group_no_pending_no_progress_calls(self) -> None:
        """Document group with no pending invites → no send call, no progress report."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("done@x.com", "fulfilled")),
        )
        client = MagicMock()
        client.get_document_group_v2.return_value = grp

        ctx = AsyncMock()

        await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None, ctx=ctx)

        ctx.report_progress.assert_not_called()

    async def test_progress_message_neutral_when_resend_fails(self) -> None:
        """A failed resend must not produce a progress message claiming the reminder was 'Sent'."""
        doc = _doc_resp(
            _doc_fi("ok@x.com", "pending", "fi-ok"),
            _doc_fi("bad@x.com", "pending", "fi-bad"),
        )
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = [None, SignNowAPIError("boom", status_code=502)]

        ctx = AsyncMock()

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        assert [r.email for r in result.failed] == ["bad@x.com"]
        messages = [c.kwargs["message"] for c in ctx.report_progress.call_args_list]
        assert messages, "expected progress to be reported for each invite"
        assert all("Sent" not in m for m in messages), f"progress falsely claims a send on failure: {messages}"


# ---------------------------------------------------------------------------
# Tests: HTTP 429 rate-limit retry on resend
# ---------------------------------------------------------------------------


def _rate_limited(message: str = "Too Many Attempts.", retry_after: float | None = None) -> SignNowAPIError:
    return SignNowAPIError(message, status_code=429, retry_after=retry_after)


class TestResendRateLimitRetry:
    """resend is retried on HTTP 429 (Too Many Attempts) with backoff; other errors fail fast."""

    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch: pytest.MonkeyPatch) -> list[float]:
        """Make backoff sleeps instant (keeps retry tests fast) and record the delays.

        Returned list captures every awaited delay so a test can assert the wait honored
        Retry-After rather than exponential backoff. Request it by name to inspect it.
        """
        calls: list[float] = []

        async def _instant(delay: float = 0.0, *_a: object, **_k: object) -> None:
            calls.append(delay)
            return None

        monkeypatch.setattr("sn_mcp_server.tools.reminder.asyncio.sleep", _instant)
        return calls

    async def test_document_resend_retries_on_429_then_succeeds(self) -> None:
        """First resend hits 429, retry succeeds → recipient reminded, not failed."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = [_rate_limited(), None]

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        assert result.failed == []
        assert client.resend_field_invite.call_count == 2

    async def test_document_resend_429_exhausted_marks_failed(self) -> None:
        """Persistent 429 across all attempts → recipient failed; call retried _RESEND_MAX_ATTEMPTS times."""
        from sn_mcp_server.tools.reminder import _RESEND_MAX_ATTEMPTS

        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = _rate_limited()

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.failed) == 1
        assert result.failed[0].email == "alice@x.com"
        assert "Too Many Attempts" in (result.failed[0].reason or "")
        assert client.resend_field_invite.call_count == _RESEND_MAX_ATTEMPTS

    async def test_non_429_error_is_not_retried(self) -> None:
        """A non-429 error fails immediately without retry."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = SignNowAPIError("server error", status_code=500)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert len(result.failed) == 1
        assert client.resend_field_invite.call_count == 1

    async def test_group_resend_retries_on_429_then_succeeds(self) -> None:
        """Group resend hits 429 then succeeds on retry → signer reminded."""
        grp = _grp_resp(_grp_doc("doc1", _grp_fi("alice@x.com", "pending")))
        client = MagicMock()
        client.get_document_group_v2.return_value = grp
        client.resend_document_group_invites.side_effect = [_rate_limited(), None]

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        assert result.failed == []
        assert client.resend_document_group_invites.call_count == 2

    async def test_429_short_retry_after_is_honored_then_succeeds(self, _no_sleep: list[float]) -> None:
        """429 with a short Retry-After → waits exactly that long (not exponential backoff), then succeeds."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = [_rate_limited(retry_after=5.0), None]

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        assert client.resend_field_invite.call_count == 2
        # Honored Retry-After in total (5s, not the 1.0s exponential backoff), split into
        # chunks no longer than the keepalive interval.
        from sn_mcp_server.tools.reminder import _RESEND_KEEPALIVE_INTERVAL_SECONDS

        assert sum(_no_sleep) == pytest.approx(5.0)
        assert _no_sleep and max(_no_sleep) <= _RESEND_KEEPALIVE_INTERVAL_SECONDS

    async def test_429_retry_after_at_cap_is_honored(self, _no_sleep: list[float]) -> None:
        """Retry-After exactly at the cap is still honored (boundary)."""
        from sn_mcp_server.tools.reminder import _RESEND_MAX_RETRY_AFTER_SECONDS

        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = [_rate_limited(retry_after=_RESEND_MAX_RETRY_AFTER_SECONDS), None]

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        assert sum(_no_sleep) == pytest.approx(_RESEND_MAX_RETRY_AFTER_SECONDS)

    async def test_429_long_retry_after_fails_fast_without_waiting(self, _no_sleep: list[float]) -> None:
        """429 with a Retry-After above the cap → fail fast (no wait, no retry), recorded as failed."""
        from sn_mcp_server.tools.reminder import _RESEND_MAX_RETRY_AFTER_SECONDS

        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = _rate_limited(retry_after=_RESEND_MAX_RETRY_AFTER_SECONDS + 1)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert result.recipients_reminded == []
        assert [r.email for r in result.failed] == ["alice@x.com"]
        assert client.resend_field_invite.call_count == 1
        assert _no_sleep == []  # never waited

    async def test_429_wait_emits_periodic_keepalive_progress(self, _no_sleep: list[float]) -> None:
        """A multi-second backoff is chunked and emits a periodic keepalive so clients don't abort the wait."""
        from sn_mcp_server.tools.reminder import _RESEND_KEEPALIVE_INTERVAL_SECONDS

        doc = _doc_resp(_doc_fi("alice@x.com", "pending", "fi-1"))
        client = MagicMock()
        client.get_document.return_value = doc
        client.resend_field_invite.side_effect = [_rate_limited(retry_after=5.0), None]

        ctx = AsyncMock()

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        assert [r.email for r in result.recipients_reminded] == ["alice@x.com"]
        # The 5s wait is honored in total, but no single silent gap exceeds the keepalive interval.
        assert sum(_no_sleep) == pytest.approx(5.0)
        assert _no_sleep and max(_no_sleep) <= _RESEND_KEEPALIVE_INTERVAL_SECONDS
        # And the client gets several heartbeats during the wait, not just one.
        waits = [m for m in (c.kwargs["message"] for c in ctx.report_progress.call_args_list) if "retrying in" in m.lower()]
        assert len(waits) >= 2, f"expected periodic keepalives during the wait, got {waits}"


class TestResendRetryDelay:
    """Pure-logic checks for _resend_retry_delay (Retry-After honoring vs exponential backoff)."""

    @pytest.mark.parametrize(
        ("retry_after", "attempt", "expected"),
        [
            (None, 1, 1.0),  # no header → exponential backoff
            (None, 2, 2.0),
            (None, 3, 4.0),
            (5.0, 1, 5.0),  # short Retry-After honored, ignores attempt
            (0.0, 1, 0.0),  # zero is honored as-is
            (-3.0, 1, 0.0),  # negative clamped to 0
            (10.0, 1, 10.0),  # exactly at cap → honored
            (10.5, 1, None),  # above cap → stop retrying
            (60.0, 2, None),
        ],
    )
    def test_delay(self, retry_after: float | None, attempt: int, expected: float | None) -> None:
        from sn_mcp_server.tools.reminder import _resend_retry_delay

        assert _resend_retry_delay(retry_after, attempt) == expected
