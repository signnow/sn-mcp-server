"""
Unit tests for reminder.py — send_invite_reminder business logic.

Mocks SignNowAPIClient with MagicMock; ctx with AsyncMock.
All sync client methods (get_document, get_document_group_v2, send_document_copy_by_email)
return/raise values set in each test.
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


def _doc_fi(email: str, status: str = "pending") -> DocumentFieldInviteStatus:
    """Minimal DocumentFieldInviteStatus for reminder.py (reads .email and .status)."""
    return DocumentFieldInviteStatus.model_construct(email=email, status=status)


def _doc_resp(*field_invites: DocumentFieldInviteStatus) -> DocumentResponse:
    """Minimal DocumentResponse for reminder.py (reads .field_invites)."""
    return DocumentResponse.model_construct(field_invites=list(field_invites))


def _grp_fi(signer_email: str, status: str = "pending") -> DocumentGroupV2FieldInvite:
    """Minimal DocumentGroupV2FieldInvite for reminder.py (reads .signer_email and .status)."""
    return DocumentGroupV2FieldInvite.model_construct(signer_email=signer_email, status=status)


def _grp_doc(doc_id: str, *field_invites: DocumentGroupV2FieldInvite) -> DocumentGroupV2Document:
    """Minimal DocumentGroupV2Document for reminder.py (reads .id and .field_invites)."""
    return DocumentGroupV2Document.model_construct(id=doc_id, field_invites=list(field_invites))


def _grp_resp(*documents: DocumentGroupV2Document) -> GetDocumentGroupV2Response:
    """Minimal GetDocumentGroupV2Response for reminder.py (reads .data.documents)."""
    data = DocumentGroupV2Data.model_construct(documents=list(documents))
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
            client.send_document_copy_by_email.side_effect = send_side_effect
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

    async def test_seven_pending_sends_two_batches(self) -> None:
        """7 pending recipients → send_document_copy_by_email called twice (5 + 2)."""
        emails = [f"user{i}@x.com" for i in range(7)]
        doc = _doc_resp(*[_doc_fi(e, "pending") for e in emails])
        client = self._client(doc)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert len(result.recipients_reminded) == 7
        assert client.send_document_copy_by_email.call_count == 2
        first_batch = client.send_document_copy_by_email.call_args_list[0].args[2]
        second_batch = client.send_document_copy_by_email.call_args_list[1].args[2]
        assert len(first_batch) == 5
        assert len(second_batch) == 2

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
        client.send_document_copy_by_email.assert_not_called()

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
        """send_document_copy_by_email raises SignNowAPIError → result.failed populated."""
        doc = _doc_resp(_doc_fi("alice@x.com", "pending"))
        err = SignNowAPIError("gateway error", status_code=502)
        client = self._client(doc, send_side_effect=err)

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None)

        assert result.recipients_reminded == []
        assert len(result.failed) == 1
        assert result.failed[0].email == "alice@x.com"
        assert DOC_ID in (result.failed[0].reason or "")


# ---------------------------------------------------------------------------
# Tests: document_group path
# ---------------------------------------------------------------------------


class TestRemindDocumentGroup:
    """Tests for _remind_document_group logic via _send_invite_reminder(entity_type='document_group')."""

    def _client(self, grp_resp: GetDocumentGroupV2Response, send_side_effect: Exception | None = None) -> MagicMock:
        client = MagicMock()
        client.get_document_group_v2.return_value = grp_resp
        if send_side_effect is not None:
            client.send_document_group_email.side_effect = send_side_effect
        return client

    async def test_pending_signers_across_docs_all_reminded(self) -> None:
        """Pending signers across multiple docs → all reminded via group send-email."""
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
        # send_document_group_email called once with group ID (not per-doc email2)
        client.send_document_group_email.assert_called_once()
        call_args = client.send_document_group_email.call_args
        assert call_args.args[1] == GRP_ID

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
        client.send_document_group_email.assert_not_called()

    async def test_email_filter_sends_only_matched_signer(self) -> None:
        """email='bob@x.com' → only bob reminded via send-email."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("bob@x.com", "pending")),
        )
        client = self._client(grp)

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", "bob@x.com", None, None)

        reminded_emails = {r.email for r in result.recipients_reminded}
        assert "bob@x.com" in reminded_emails
        assert "alice@x.com" not in reminded_emails

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
        """send_document_group_email raises SignNowAPIError → result.failed populated."""
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

    async def test_send_email_request_payload_structure(self) -> None:
        """Verify send_document_group_email called with correct SendEmailRequest fields."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("bob@x.com", "pending")),
        )
        client = self._client(grp)

        await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None)

        # Verify the SendEmailRequest passed to the client
        call_args = client.send_document_group_email.call_args
        request_data = call_args.args[2]  # 3rd positional arg: request_data
        # Should have to=[{"email": "alice@x.com"}, {"email": "bob@x.com"}]
        assert len(request_data.to) == 2
        to_emails = {r["email"] for r in request_data.to}
        assert to_emails == {"alice@x.com", "bob@x.com"}


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
    """Tests for ctx.report_progress calls during batched email2 sends."""

    async def test_progress_called_once_per_batch(self) -> None:
        """7 emails → 2 batches → ctx.report_progress called twice with correct total."""
        emails = [f"user{i}@x.com" for i in range(7)]
        doc = _doc_resp(*[_doc_fi(e, "pending") for e in emails])
        client = MagicMock()
        client.get_document.return_value = doc

        ctx = AsyncMock()

        result = await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        assert len(result.recipients_reminded) == 7
        assert ctx.report_progress.call_count == 2
        # Both calls should pass total=2
        for progress_call in ctx.report_progress.call_args_list:
            assert progress_call.kwargs["total"] == 2

    async def test_single_batch_reports_once(self) -> None:
        """3 emails → 1 batch → ctx.report_progress called exactly once."""
        emails = [f"user{i}@x.com" for i in range(3)]
        doc = _doc_resp(*[_doc_fi(e, "pending") for e in emails])
        client = MagicMock()
        client.get_document.return_value = doc

        ctx = AsyncMock()

        await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        assert ctx.report_progress.call_count == 1
        assert ctx.report_progress.call_args.kwargs["total"] == 1

    async def test_no_pending_no_progress_calls(self) -> None:
        """No pending invites → no send batches → ctx.report_progress never called."""
        doc = _doc_resp(_doc_fi("done@x.com", "fulfilled"))
        client = MagicMock()
        client.get_document.return_value = doc

        ctx = AsyncMock()

        await _send_invite_reminder(client, TOKEN, DOC_ID, "document", None, None, None, ctx=ctx)

        ctx.report_progress.assert_not_called()

    async def test_group_send_email_reports_progress_once(self) -> None:
        """Document group send-email → ctx.report_progress called once (single API call)."""
        grp = _grp_resp(
            _grp_doc("doc1", _grp_fi("alice@x.com", "pending"), _grp_fi("bob@x.com", "pending")),
        )
        client = MagicMock()
        client.get_document_group_v2.return_value = grp

        ctx = AsyncMock()

        result = await _send_invite_reminder(client, TOKEN, GRP_ID, "document_group", None, None, None, ctx=ctx)

        assert len(result.recipients_reminded) == 2
        assert ctx.report_progress.call_count == 1
        assert ctx.report_progress.call_args.kwargs["total"] == 1

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
