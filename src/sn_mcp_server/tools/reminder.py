"""
Send invite reminder business logic for SignNow MCP server.

Sends signing reminders to pending signers on documents and document groups.
- Documents: POST /document/{id}/email2 (send document copy by email), batched by 5.
- Document groups: POST /v2/document-groups/{id}/send-email (native group endpoint).

Supports auto-detection of entity type (document_group tried first, document as fallback).
"""

from __future__ import annotations

import time

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import GetDocumentGroupV2Response
from signnow_client.models.templates_and_documents import DocumentResponse, SendEmailRequest

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
    and sends reminders:
    - Documents: calls send_document_copy_by_email (POST /document/{id}/email2) in batches of 5.
    - Document groups: calls send_document_group_email (POST /v2/document-groups/{id}/send-email) once.

    Auto-detection order: document_group (v2) first (modern), document as legacy fallback.
    Non-404 API errors propagate immediately without attempting fallback.

    For document groups: collects all pending signers across all documents in the group.

    Reports progress via ctx.report_progress when ctx is provided
    (AGENTS.md requirement: report progress for every API call in a loop).

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
    """Build and send reminders for a document group via POST /v2/document-groups/{id}/send-email.

    Collects all pending signers across every document in the group. Uses the native
    document-group send-email endpoint — a single API call for the entire group (no
    per-document batching).

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: Document group ID.
        group_response: GetDocumentGroupV2Response from client.get_document_group_v2().
        email: Optional single-recipient filter.
        subject: Optional email subject (not used by send-email endpoint; reserved for future use).
        message: Optional email body (not used by send-email endpoint; reserved for future use).
        ctx: Optional MCP Context for progress reporting.

    Returns:
        SendReminderResponse with entity_type='document_group'.
    """
    pending_emails: list[str] = []
    all_signer_emails: set[str] = set()
    skipped: list[ReminderRecipientResult] = []

    for doc in group_response.data.documents:
        for fi in doc.field_invites:
            all_signer_emails.add(fi.signer_email)
            status = InviteStatusValues.from_raw_status(fi.status)
            is_pending = status in _PENDING_STATUSES

            if email is not None and fi.signer_email != email:
                continue

            if is_pending:
                if fi.signer_email not in pending_emails:
                    pending_emails.append(fi.signer_email)
            else:
                skipped.append(
                    ReminderRecipientResult(
                        email=fi.signer_email,
                        document_id=doc.id,
                        reason=f"invite status: {status}",
                    )
                )

    if not pending_emails:
        if email is not None:
            if email not in all_signer_emails:
                skipped.append(
                    ReminderRecipientResult(
                        email=email,
                        reason=f"no pending invite found for {email} in document_group {entity_id}",
                    )
                )
            elif not any(s.email == email for s in skipped):
                skipped.append(
                    ReminderRecipientResult(
                        email=email,
                        reason=f"invite for {email} is not pending in document_group {entity_id}",
                    )
                )
        else:
            skipped = [ReminderRecipientResult(email=se, reason="no pending invite in group") for se in all_signer_emails]

        return SendReminderResponse(
            entity_id=entity_id,
            entity_type="document_group",
            skipped=skipped,
        )

    # Build SendEmailRequest payload for the native group send-email endpoint.
    request_data = SendEmailRequest(
        to=[{"email": addr} for addr in pending_emails],
        with_history=False,
        client_timestamp=int(time.time()),
    )

    reminded: list[ReminderRecipientResult] = []
    failed: list[ReminderRecipientResult] = []

    try:
        client.send_document_group_email(token, entity_id, request_data)
        for addr in pending_emails:
            reminded.append(ReminderRecipientResult(email=addr))
    except SignNowAPIError as err:
        for addr in pending_emails:
            failed.append(
                ReminderRecipientResult(
                    email=addr,
                    reason=f"Failed to send reminder for document_group {entity_id}: {err}",
                )
            )

    if ctx is not None:
        await ctx.report_progress(
            progress=1,
            total=1,
            message="Sent group reminder",
        )

    return SendReminderResponse(
        entity_id=entity_id,
        entity_type="document_group",
        recipients_reminded=reminded,
        skipped=skipped,
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
