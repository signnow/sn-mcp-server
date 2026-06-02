"""
Send invite reminder business logic for SignNow MCP server.

Sends signing reminders to pending signers on documents and document groups by resending
their pending invites — the same actions the SignNow web app fires from its "Send reminder"
buttons:
- Documents: PUT /fieldinvite/{field_invite_id}/resend, once per pending field invite.
- Document groups: POST /documentgroup/{id}/groupinvite/{invite_id}/resendinvites, once per pending signer.

Supports auto-detection of entity type (document_group tried first, document as fallback).

The resend endpoints reuse each invite's original email template, so they take no custom
subject/message. Those tool parameters are kept for input-contract stability but are not
forwarded to the API.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from functools import partial

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import GetDocumentGroupV2Response, ResendDocumentGroupInvitesRequest
from signnow_client.models.templates_and_documents import DocumentResponse, ResendFieldInviteRequest

from .models import InviteStatusValues, ReminderRecipientResult, SendReminderResponse

_PENDING_STATUSES = {InviteStatusValues.PENDING, InviteStatusValues.CREATED}

# SignNow rate-limits resends (HTTP 429 "Too Many Attempts"). Bulk reminder loops resend
# once per pending invite/signer in quick succession, so a 429 can hit partway through.
# Retry only the rate-limited call; other errors fail fast.
_RESEND_RATE_LIMIT_STATUS = 429
_RESEND_MAX_ATTEMPTS = 3
_RESEND_BACKOFF_SECONDS = 1.0
# When SignNow sends a Retry-After we honor it — but only if the wait is short enough to
# block the tool call for. A larger Retry-After means we stop retrying and record the
# recipient as failed (the agent can retry the whole reminder later) rather than hang.
_RESEND_MAX_RETRY_AFTER_SECONDS = 10.0


def _resend_retry_delay(retry_after: float | None, attempt: int) -> float | None:
    """Seconds to wait before the next resend retry, or None to stop retrying.

    Honors the server's Retry-After when present and within
    `_RESEND_MAX_RETRY_AFTER_SECONDS`; a larger Retry-After returns None so the caller
    gives up rather than block the tool call. Without a Retry-After, falls back to
    exponential backoff (`_RESEND_BACKOFF_SECONDS * 2**(attempt-1)`).

    Args:
        retry_after: Server-requested backoff in seconds (SignNowAPIError.retry_after), or None.
        attempt: 1-based attempt number that just failed, for the backoff curve.

    Returns:
        Non-negative delay in seconds, or None to stop retrying.
    """
    if retry_after is not None:
        if retry_after > _RESEND_MAX_RETRY_AFTER_SECONDS:
            return None
        return max(retry_after, 0.0)
    return _RESEND_BACKOFF_SECONDS * (2.0 ** (attempt - 1))


async def _resend_with_retry(send: Callable[[], object]) -> None:
    """Invoke a resend callable, retrying on HTTP 429 with backoff.

    On a 429 (rate limit) the call is retried up to `_RESEND_MAX_ATTEMPTS` times. The
    wait between tries honors the server's Retry-After when present (see
    `_resend_retry_delay`), otherwise uses exponential backoff. Any non-429
    SignNowAPIError, a 429 on the final attempt, or a Retry-After longer than
    `_RESEND_MAX_RETRY_AFTER_SECONDS` propagates to the caller, which records the
    recipient as failed.

    Args:
        send: Zero-argument callable performing one resend (raises SignNowAPIError on error).
    """
    for attempt in range(1, _RESEND_MAX_ATTEMPTS + 1):
        try:
            send()
            return
        except SignNowAPIError as err:
            if err.status_code != _RESEND_RATE_LIMIT_STATUS or attempt >= _RESEND_MAX_ATTEMPTS:
                raise
            delay = _resend_retry_delay(err.retry_after, attempt)
            if delay is None:
                # Server asked us to wait longer than we are willing to block — fail fast.
                raise
            await asyncio.sleep(delay)


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
    and resends their invites:
    - Documents: calls resend_field_invite (PUT /fieldinvite/{id}/resend) per pending field invite.
    - Document groups: calls resend_document_group_invites
      (POST /documentgroup/{id}/groupinvite/{invite_id}/resendinvites) per pending signer.

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
        subject: Accepted for input-contract stability; the resend endpoints reuse the
            invite's original email template, so this is not applied.
        message: Accepted for input-contract stability; not applied (see subject).
        ctx: Optional MCP Context for progress reporting (None in unit tests).

    Returns:
        SendReminderResponse with categorised recipients.

    Raises:
        ValueError: entity_type value is invalid, or entity not found during auto-detection (both 404).
        SignNowAPIError: Any API error when entity_type is explicit; non-404 errors during auto-detection.
    """
    # subject/message are part of the tool's stable input contract but the resend endpoints
    # reuse each invite's original email template, so they are intentionally not forwarded.
    del subject, message

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
        return await _remind_document_group(client, token, entity_id, group_response, email, ctx)

    # entity_type == "document" (legacy path)
    if doc_response is None:
        doc_response = client.get_document(token, entity_id)
    return await _remind_document(client, token, entity_id, doc_response, email, ctx)


async def _remind_document(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    doc_response: DocumentResponse,
    email: str | None,
    ctx: Context | None,
) -> SendReminderResponse:
    """Resend pending field invites for a single document.

    Resends each pending field invite via PUT /fieldinvite/{id}/resend (one call per invite).

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: Document ID.
        doc_response: DocumentResponse from client.get_document().
        email: Optional single-recipient filter.
        ctx: Optional MCP Context for progress reporting.

    Returns:
        SendReminderResponse with entity_type='document'.
    """
    pending_invites: list[tuple[str, str]] = []  # (field_invite_id, signer_email)
    skipped: list[ReminderRecipientResult] = []

    for fi in doc_response.field_invites:
        status = InviteStatusValues.from_raw_status(fi.status)
        is_pending = status in _PENDING_STATUSES

        if email is not None and fi.email != email:
            # Filtered out by caller — do not report in skipped
            continue

        if is_pending:
            pending_invites.append((fi.id, fi.email))
        else:
            skipped.append(
                ReminderRecipientResult(
                    email=fi.email,
                    document_id=entity_id,
                    reason=f"invite status: {status}",
                )
            )

    # An email with at least one pending invite is reminded, so it must not also appear in
    # skipped because of a separate non-pending invite for the same address.
    pending_addresses = {addr for _, addr in pending_invites}
    skipped = [s for s in skipped if s.email not in pending_addresses]

    if email is not None and not pending_invites and not any(s.email == email for s in skipped):
        skipped.append(
            ReminderRecipientResult(
                email=email,
                document_id=entity_id,
                reason=f"no invite found for {email} on document {entity_id}",
            )
        )

    reminded, failed = await _resend_field_invites(client, token, entity_id, pending_invites, ctx)

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
    ctx: Context | None,
) -> SendReminderResponse:
    """Resend group invites for a document group via POST /documentgroup/{id}/groupinvite/{invite_id}/resendinvites.

    Collects all pending signers across every document in the group and resends the group
    invite to each one (one call per pending signer). Requires an active group invite —
    GetDocumentGroupV2Response.data.invite_id; if absent, all pending signers are reported
    as failed.

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: Document group ID.
        group_response: GetDocumentGroupV2Response from client.get_document_group_v2().
        email: Optional single-recipient filter.
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

    # A signer pending on any document is reminded once via the group-level resend, so a
    # non-pending invite for the same signer on another document must not also land them in
    # skipped — an email must never appear in both recipients_reminded and skipped.
    pending_set = set(pending_emails)
    skipped = [s for s in skipped if s.email not in pending_set]

    if not pending_emails:
        if email is not None:
            if email not in all_signer_emails:
                skipped.append(
                    ReminderRecipientResult(
                        email=email,
                        reason=f"no invite found for {email} in document_group {entity_id}",
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

    reminded: list[ReminderRecipientResult] = []
    failed: list[ReminderRecipientResult] = []

    group_invite_id = group_response.data.invite_id
    if group_invite_id is None:
        # No active invite to resend — surface every pending signer as failed (retryable).
        for addr in pending_emails:
            failed.append(
                ReminderRecipientResult(
                    email=addr,
                    reason=f"no active invite to resend for document_group {entity_id}",
                )
            )
        return SendReminderResponse(
            entity_id=entity_id,
            entity_type="document_group",
            recipients_reminded=reminded,
            skipped=skipped,
            failed=failed,
        )

    total = len(pending_emails)
    for idx, addr in enumerate(pending_emails, start=1):
        request_data = ResendDocumentGroupInvitesRequest(email=addr, client_timestamp=int(time.time()))
        try:
            await _resend_with_retry(partial(client.resend_document_group_invites, token, entity_id, group_invite_id, request_data))
            reminded.append(ReminderRecipientResult(email=addr))
        except SignNowAPIError as err:
            failed.append(
                ReminderRecipientResult(
                    email=addr,
                    reason=f"Failed to send reminder for document_group {entity_id}: {err}",
                )
            )
        if ctx is not None:
            await ctx.report_progress(
                progress=idx,
                total=total,
                message=f"Processed group reminder {idx}/{total}",
            )

    return SendReminderResponse(
        entity_id=entity_id,
        entity_type="document_group",
        recipients_reminded=reminded,
        skipped=skipped,
        failed=failed,
    )


async def _resend_field_invites(
    client: SignNowAPIClient,
    token: str,
    document_id: str,
    invites: list[tuple[str, str]],
    ctx: Context | None,
) -> tuple[list[ReminderRecipientResult], list[ReminderRecipientResult]]:
    """Resend pending field invites one at a time via PUT /fieldinvite/{id}/resend.

    Reports progress after each call when ctx is provided.

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        document_id: Document ID the invites belong to.
        invites: List of (field_invite_id, signer_email) for each pending invite.
        ctx: Optional MCP Context for progress reporting.

    Returns:
        Tuple of (reminded, failed) lists of ReminderRecipientResult.
    """
    reminded: list[ReminderRecipientResult] = []
    failed: list[ReminderRecipientResult] = []

    total = len(invites)
    for idx, (field_invite_id, addr) in enumerate(invites, start=1):
        request_data = ResendFieldInviteRequest(client_timestamp=int(time.time()))
        try:
            await _resend_with_retry(partial(client.resend_field_invite, token, field_invite_id, request_data))
            reminded.append(ReminderRecipientResult(email=addr, document_id=document_id))
        except SignNowAPIError as err:
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
                message=f"Processed reminder {idx}/{total}",
            )

    return reminded, failed
