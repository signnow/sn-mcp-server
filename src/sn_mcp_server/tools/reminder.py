"""
Send invite reminder business logic for SignNow MCP server.

Sends signing reminders to pending signers by calling POST /document/{id}/email2
(send document copy by email). Supports both documents and document groups with
auto-detection of entity type (document_group tried first, document as fallback).
"""

from __future__ import annotations

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import GetDocumentGroupV2Response
from signnow_client.models.templates_and_documents import DocumentResponse

from .models import InviteStatusValues, ReminderRecipientResult, SendReminderResponse

_PENDING_STATUSES = {InviteStatusValues.PENDING, InviteStatusValues.CREATED}


async def _send_invite_reminder(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    entity_type: str | None,
    email: str | None,
    subject: str | None,
    message: str | None,
    ctx: Context | None = None,
) -> SendReminderResponse:
    """Send signing reminders to pending signers on a document or document group.

    Resolves entity type (auto-detects if not provided), determines pending signers,
    and calls send_document_copy_by_email in batches of at most 5 per API call.

    Auto-detection order: document_group (v2) first (modern), document as legacy fallback.
    Non-404 API errors propagate immediately without attempting fallback.

    For document_group: targets only the first document with pending invites.
    Pending signers on subsequent documents in the group are not included in any output list.

    Reports progress via ctx.report_progress before each email2 batch call when ctx is
    provided (AGENTS.md requirement: report progress for every API call in a loop).

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: Document or document group ID.
        entity_type: 'document' | 'document_group' | None (auto-detect).
        email: Optional filter — remind only this recipient.
        subject: Optional email subject for the reminder.
        message: Optional email body for the reminder.
        ctx: Optional MCP Context for progress reporting (None in unit tests).

    Returns:
        SendReminderResponse with categorised recipients.

    Raises:
        ValueError: entity_type value is invalid, or entity not found during auto-detection (both 404).
        SignNowAPIError: Any API error when entity_type is explicit; non-404 errors during auto-detection.
    """
    if entity_type is not None and entity_type not in {"document", "document_group"}:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'document' or 'document_group'.")

    group_response = None
    doc_response = None

    if entity_type is None:
        # Auto-detection: try document_group first (modern), fall back to document (legacy).
        try:
            group_response = client.get_document_group_v2(token, entity_id)
            entity_type = "document_group"
        except SignNowAPIError as exc:
            if exc.status_code != 404:
                # Non-404 errors (401, 403, 429, 500…) must not be swallowed.
                raise
            # 404 on group: try document path.
            try:
                doc_response = client.get_document(token, entity_id)
                entity_type = "document"
            except SignNowAPIError as exc2:
                if exc2.status_code != 404:
                    raise
                raise ValueError(f"Entity {entity_id} not found as document or document_group") from None

    if entity_type == "document_group":
        if group_response is None:
            group_response = client.get_document_group_v2(token, entity_id)
        return await _remind_document_group(client, token, entity_id, group_response, email, subject, message, ctx)

    # entity_type == "document" (legacy path)
    if doc_response is None:
        doc_response = client.get_document(token, entity_id)
    return await _remind_document(client, token, entity_id, doc_response, email, subject, message, ctx)


async def _remind_document(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    doc_response: DocumentResponse,
    email: str | None,
    subject: str | None,
    message: str | None,
    ctx: Context | None,
) -> SendReminderResponse:
    """Build and send reminders for a single document.

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: Document ID.
        doc_response: DocumentResponse from client.get_document().
        email: Optional single-recipient filter.
        subject: Optional email subject.
        message: Optional email body.
        ctx: Optional MCP Context for progress reporting.

    Returns:
        SendReminderResponse with entity_type='document'.
    """
    pending_emails: list[str] = []
    skipped: list[ReminderRecipientResult] = []

    for fi in doc_response.field_invites:
        status = InviteStatusValues.from_raw_status(fi.status)
        is_pending = status in _PENDING_STATUSES

        if email is not None and fi.email != email:
            # Filtered out by caller — do not report in skipped
            continue

        if is_pending:
            pending_emails.append(fi.email)
        else:
            skipped.append(
                ReminderRecipientResult(
                    email=fi.email,
                    document_id=entity_id,
                    reason=f"invite status: {status}",
                )
            )

    if email is not None and not pending_emails and not any(s.email == email for s in skipped):
        skipped.append(
            ReminderRecipientResult(
                email=email,
                document_id=entity_id,
                reason=f"no pending invite found for {email} on document {entity_id}",
            )
        )

    reminded, failed = await _send_in_batches(client, token, entity_id, pending_emails, subject, message, ctx)

    return SendReminderResponse(
        entity_id=entity_id,
        entity_type="document",
        recipients_reminded=reminded,
        skipped=skipped,
        failed=failed,
    )


async def _remind_document_group(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    group_response: GetDocumentGroupV2Response,
    email: str | None,
    subject: str | None,
    message: str | None,
    ctx: Context | None,
) -> SendReminderResponse:
    """Build and send reminders for a document group.

    Processes only the first document with pending invites (matching the optional email
    filter). Pending signers on subsequent documents are not included in any output list.

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: Document group ID.
        group_response: GetDocumentGroupV2Response from client.get_document_group_v2().
        email: Optional single-recipient filter.
        subject: Optional email subject.
        message: Optional email body.
        ctx: Optional MCP Context for progress reporting.

    Returns:
        SendReminderResponse with entity_type='document_group'.
    """
    first_pending_doc = None
    pending_emails: list[str] = []
    all_signer_emails: set[str] = set()
    skipped_on_first_doc: list[ReminderRecipientResult] = []

    for doc in group_response.data.documents:
        for fi in doc.field_invites:
            all_signer_emails.add(fi.signer_email)

            if first_pending_doc is not None and doc.id != first_pending_doc.id:
                # Only process invites on the first pending document found.
                continue

            status = InviteStatusValues.from_raw_status(fi.status)
            is_pending = status in _PENDING_STATUSES

            if not is_pending:
                # Track non-pending signers on the first pending doc for skipped output.
                if first_pending_doc is None or doc.id == first_pending_doc.id:
                    if email is None or fi.signer_email == email:
                        skipped_on_first_doc.append(
                            ReminderRecipientResult(
                                email=fi.signer_email,
                                document_id=doc.id,
                                reason=f"invite status: {InviteStatusValues.from_raw_status(fi.status)}",
                            )
                        )
                continue

            if email is not None and fi.signer_email != email:
                # Filtered by caller — skip to next invite
                continue

            if first_pending_doc is None:
                first_pending_doc = doc

            if doc.id == first_pending_doc.id:
                pending_emails.append(fi.signer_email)

    if first_pending_doc is None:
        # No pending document found.
        skipped: list[ReminderRecipientResult] = []
        if email is not None:
            # Email filter was specified but didn't match any pending signer.
            # Only report the filtered email — don't dump all signers as "no pending".
            if email not in all_signer_emails:
                skipped.append(
                    ReminderRecipientResult(
                        email=email,
                        reason=f"no pending invite found for {email} in document_group {entity_id}",
                    )
                )
            else:
                skipped.append(
                    ReminderRecipientResult(
                        email=email,
                        reason=f"invite for {email} is not pending in document_group {entity_id}",
                    )
                )
        else:
            # No email filter — all signers are truly non-pending, report them.
            skipped = [ReminderRecipientResult(email=se, reason="no pending invite in group") for se in all_signer_emails]
        return SendReminderResponse(
            entity_id=entity_id,
            entity_type="document_group",
            skipped=skipped,
        )

    doc_id = first_pending_doc.id
    reminded, failed = await _send_in_batches(client, token, doc_id, pending_emails, subject, message, ctx)

    return SendReminderResponse(
        entity_id=entity_id,
        entity_type="document_group",
        recipients_reminded=reminded,
        skipped=skipped_on_first_doc,
        failed=failed,
    )


async def _send_in_batches(
    client: SignNowAPIClient,
    token: str,
    document_id: str,
    emails: list[str],
    subject: str | None,
    message: str | None,
    ctx: Context | None,
) -> tuple[list[ReminderRecipientResult], list[ReminderRecipientResult]]:
    """Send reminder emails in batches of at most 5.

    Reports progress after each batch call when ctx is provided.

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        document_id: Document ID to remind for.
        emails: Full list of pending recipient emails.
        subject: Optional email subject.
        message: Optional email body.
        ctx: Optional MCP Context for progress reporting.

    Returns:
        Tuple of (reminded, failed) lists of ReminderRecipientResult.
    """
    reminded: list[ReminderRecipientResult] = []
    failed: list[ReminderRecipientResult] = []

    chunks = [emails[i : i + 5] for i in range(0, len(emails), 5)]
    total = len(chunks)

    for idx, chunk in enumerate(chunks, start=1):
        try:
            client.send_document_copy_by_email(token, document_id, chunk, message, subject)
            for addr in chunk:
                reminded.append(ReminderRecipientResult(email=addr, document_id=document_id))
        except SignNowAPIError as err:
            for addr in chunk:
                failed.append(
                    ReminderRecipientResult(
                        email=addr,
                        document_id=document_id,
                        reason=f"Failed to send reminder for document {document_id}: {err}",
                    )
                )
        if ctx is not None:
            await ctx.report_progress(
                progress=idx,
                total=total,
                message=f"Sent reminder batch {idx}/{total}",
            )

    return reminded, failed
