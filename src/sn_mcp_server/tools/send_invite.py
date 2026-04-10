"""
Send invite functions for SignNow MCP server.

This module contains functions for sending invites to sign documents and document groups
from the SignNow API.
"""

from typing import Any, Literal

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError, SignNowAPIHTTPError

from .models import InviteOrder, SendInviteResponse
from .utils import _is_not_found_error


def _send_document_group_field_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[Any], document_group: Any) -> SendInviteResponse:
    """Private function to send document group field invite."""
    from signnow_client import (
        CreateFieldInviteRequest,
        FieldInviteAction,
        FieldInviteEmail,
        FieldInviteReminder,
        FieldInviteStep,
    )

    # Convert orders to field invite steps
    invite_steps = []
    for order_info in orders:
        actions = []
        invite_emails = []

        for recipient in order_info.recipients:
            # Create FieldInviteEmail for each recipient
            invite_email_kwargs: dict[str, Any] = {
                "email": recipient.email,
                "subject": recipient.subject,
                "message": recipient.message,
                # ALWAYS pass expiration_days to override the API model's Field(30) default.
                # When recipient.expiration_days is None, the model receives None which is
                # excluded from the serialised payload, so SignNow uses the account default.
                "expiration_days": recipient.expiration_days,
            }
            if recipient.reminder:
                invite_email_kwargs["reminder"] = FieldInviteReminder(
                    remind_after=recipient.reminder.remind_after,
                    remind_before=recipient.reminder.remind_before,
                    remind_repeat=recipient.reminder.remind_repeat,
                )
            invite_email = FieldInviteEmail(**invite_email_kwargs)
            invite_emails.append(invite_email)

            # Create FieldInviteAction only for documents with matching roles
            for document in document_group.documents:
                # Only create action if the document has the required role
                if recipient.role in document.roles:
                    # Only include redirect_target if redirect_uri is provided
                    action_data = {
                        "email": recipient.email,
                        "role_name": recipient.role,
                        "action": recipient.action,
                        "document_id": document.id,  # Use actual document ID from the group
                        "redirect_uri": recipient.redirect_uri,
                        "decline_redirect_uri": recipient.decline_redirect_uri,
                        "close_redirect_uri": recipient.close_redirect_uri,
                    }

                    # Only add redirect_target if redirect_uri is provided and not empty
                    if recipient.redirect_uri and recipient.redirect_uri.strip():
                        action_data["redirect_target"] = recipient.redirect_target

                    action = FieldInviteAction(**action_data)
                    actions.append(action)

        step = FieldInviteStep(order=order_info.order, invite_emails=invite_emails, invite_actions=actions)  # All recipients' emails with their subjects and messages
        invite_steps.append(step)

    request_data = CreateFieldInviteRequest(invite_steps=invite_steps, cc=[], cc_subject=None, cc_message=None)  # TODO: Add CC support if needed

    response = client.create_field_invite(token, entity_id, request_data)

    return SendInviteResponse(invite_id=response.id, invite_entity="document_group")


def _send_document_field_invite(client: SignNowAPIClient, token: str, entity_id: str, orders: list[Any]) -> SendInviteResponse:
    """Private function to send document field invite."""
    from signnow_client import (
        CreateDocumentFieldInviteRequest,
        DocumentFieldInviteRecipient,
        DocumentFieldInviteReminder,
    )

    # Get user info to use primary email as 'from' address
    user_info = client.get_user_info(token)
    from_email = user_info.primary_email

    # Convert orders to document field invite recipients
    recipients = []
    for order_info in orders:
        for recipient in order_info.recipients:
            # Create DocumentFieldInviteRecipient for each recipient
            recipient_data = {
                "email": recipient.email,
                "role": recipient.role,
                "order": order_info.order,
                "redirect_uri": recipient.redirect_uri,
                "decline_by_signature": "1" if recipient.decline_redirect_uri else "0",
                "subject": recipient.subject,
                "message": recipient.message,
            }

            # Only add redirect_target if redirect_uri is provided and not empty
            if recipient.redirect_uri and recipient.redirect_uri.strip():
                recipient_data["redirect_target"] = recipient.redirect_target

            if recipient.reminder:
                recipient_data["reminder"] = DocumentFieldInviteReminder(
                    remind_after=recipient.reminder.remind_after,
                    remind_before=recipient.reminder.remind_before,
                    remind_repeat=recipient.reminder.remind_repeat,
                )
            # ALWAYS pass expiration_days to override the API model's Field(30) default.
            # When recipient.expiration_days is None, the model receives None which is
            # excluded from the serialised payload, so SignNow uses the account default.
            recipient_data["expiration_days"] = recipient.expiration_days

            doc_recipient = DocumentFieldInviteRecipient(**recipient_data)
            recipients.append(doc_recipient)

    # Create document field invite request
    request_data = CreateDocumentFieldInviteRequest(document_id=entity_id, to=recipients, from_=from_email)

    response = client.create_document_field_invite(token, entity_id, request_data)

    return SendInviteResponse(invite_id=response.status, invite_entity="document")  # Document field invite returns status, not id


def _detect_send_invite_entity_type(
    entity_id: str,
    token: str,
    client: SignNowAPIClient,
) -> tuple[Literal["document", "document_group", "template", "template_group"], Any]:
    """Detect the entity type for the given ID using a 4-probe waterfall.

    Probe order (stops at first match, re-raises non-detection errors):
      1. get_document_group   → "document_group" (returns loaded group as side-effect)
      2. get_document_group_template → "template_group"
      3. get_document         → "document"
      4. (no probe)           → "template" (last resort)

    Args:
        entity_id: ID to classify
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        Tuple of (entity_type, preloaded_group) where preloaded_group is the
        GetDocumentGroupResponse when type is "document_group", None otherwise.
    """
    # Probe 1: document group
    try:
        group = client.get_document_group(token, entity_id)
        return ("document_group", group)
    except SignNowAPIError as exc:
        if exc.status_code != 404:
            raise

    # Probe 2: template group (SignNow returns 400/65582 or 404 when not found)
    try:
        client.get_document_group_template(token, entity_id)
        return ("template_group", None)
    except SignNowAPIHTTPError as exc:
        if exc.status_code != 404 and not _is_not_found_error(exc):
            raise
    except SignNowAPIError as exc:
        if exc.status_code != 404:
            raise

    # Probe 3: document
    try:
        client.get_document(token, entity_id)
        return ("document", None)
    except SignNowAPIError as exc:
        if exc.status_code != 404:
            raise

    # Probe 4: last resort — assume template; creation will surface the error if wrong
    return ("template", None)


async def _send_invite(
    entity_id: str,
    entity_type: Literal["document", "document_group", "template", "template_group"] | None,
    orders: list[InviteOrder],
    token: str,
    client: SignNowAPIClient,
    name: str | None = None,
    ctx: Context | None = None,
) -> SendInviteResponse:
    """Send invite to sign a document, document group, template, or template group.

    When entity_type is 'template' or 'template_group', creates a document/group
    from the template first, then sends the invite on the created entity.

    Args:
        entity_id: ID of the document, document group, template, or template group
        entity_type: Entity type (optional, auto-detected if None)
        orders: List of orders with recipients
        token: Access token for SignNow API
        client: SignNow API client instance
        name: Optional name for the new entity (used only for template/template_group)
        ctx: FastMCP context for progress reporting (used for template flows)

    Returns:
        SendInviteResponse with invite details and optional created entity info
    """
    created_entity_id: str | None = None
    created_entity_type: str | None = None
    created_entity_name: str | None = None
    preloaded_group: Any = None
# define entity type > template or tg > doc docgroup invite
    if entity_type in ("template", "template_group"):
        # Step 1: create document/group from template
        if ctx:
            await ctx.report_progress(progress=1, total=3)

        from .create_from_template import _create_from_template

        created = _create_from_template(entity_id, entity_type, name, token, client)

        if ctx:
            await ctx.report_progress(progress=2, total=3)

        created_entity_id = created.entity_id
        created_entity_type = created.entity_type
        created_entity_name = created.name
        entity_id = created.entity_id
        entity_type = created.entity_type  # now "document" or "document_group"

    elif entity_type is None:
        # Auto-detect using 4-probe waterfall
        entity_type, preloaded_group = _detect_send_invite_entity_type(entity_id, token, client)

        if entity_type in ("template", "template_group"):
            # Recurse with the detected type to follow the template creation path
            return await _send_invite(entity_id, entity_type, orders, token, client, name, ctx)

    # Dispatch to document_group or document invite path
    if entity_type == "document_group":
        group = preloaded_group or client.get_document_group(token, entity_id)
        invite_response = _send_document_group_field_invite(client, token, entity_id, orders, group)
    else:
        invite_response = _send_document_field_invite(client, token, entity_id, orders)

    if ctx and created_entity_id:
        await ctx.report_progress(progress=3, total=3)

    return SendInviteResponse(
        invite_id=invite_response.invite_id,
        invite_entity=invite_response.invite_entity,
        created_entity_id=created_entity_id,
        created_entity_type=created_entity_type,
        created_entity_name=created_entity_name,
    )
