"""
Send invite functions for SignNow MCP server.

This module contains functions for sending invites to sign documents and document groups
from the SignNow API.
"""

from typing import Any, Literal, cast

from fastmcp import Context

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import GetDocumentGroupResponse
from signnow_client.models.templates_and_documents import FieldInviteAuthentication
from .models import InviteOrder, SendInviteResponse, SignerAuthentication
from sn_mcp_server.tools.create_from_template import _resolve_entity
from .models import InviteOrder, SendInviteResponse
from .utils import _detect_entity_type


def _build_document_auth_kwargs(authentication: SignerAuthentication | None) -> dict[str, Any]:
    """Build authentication kwargs for DocumentFieldInviteRecipient.

    Pure transformation — no validation, no network calls.
    SignerAuthentication's @model_validator guarantees required credentials are
    present before this function is called. Returns an empty dict when
    authentication is None so the caller can unconditionally call .update().
    """
    if authentication is None:
        return {}
    kwargs: dict[str, Any] = {"authentication_type": authentication.type}
    if authentication.type == "password":
        kwargs["password"] = authentication.password
    elif authentication.type == "phone":
        kwargs["phone"] = authentication.phone
        # Always set method — even when None — so it overrides the DocumentFieldInviteRecipient
        # field default of 'sms'. A None value is then dropped by model_dump(exclude_none=True),
        # meaning the key is omitted from the API request when not explicitly specified.
        kwargs["method"] = authentication.method
        if authentication.sms_message:
            kwargs["authentication_sms_message"] = authentication.sms_message
    return kwargs


def _build_field_invite_authentication(authentication: SignerAuthentication | None) -> FieldInviteAuthentication | None:
    """Convert tool-layer SignerAuthentication to signnow_client FieldInviteAuthentication.

    Pure transformation — no validation, no network calls.
    SignerAuthentication's @model_validator guarantees required credentials are
    present before this function is called. Returns None when authentication is
    None so the caller can guard with 'if field_auth is not None'.
    """
    if authentication is None:
        return None
    if authentication.type == "password":
        return FieldInviteAuthentication(type="password", value=authentication.password)
    # type == "phone": set both value and phone for maximum SignNow API compatibility
    return FieldInviteAuthentication(
        type="phone",
        value=authentication.phone,
        phone=authentication.phone,
        method=authentication.method,
        message=authentication.sms_message,
    )


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

                    field_auth = _build_field_invite_authentication(recipient.authentication)
                    if field_auth is not None:
                        action_data["authentication"] = field_auth

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
            recipient_data.update(_build_document_auth_kwargs(recipient.authentication))

            doc_recipient = DocumentFieldInviteRecipient(**recipient_data)
            recipients.append(doc_recipient)

    # Create document field invite request
    request_data = CreateDocumentFieldInviteRequest(document_id=entity_id, to=recipients, from_=from_email)

    response = client.create_document_field_invite(token, entity_id, request_data)

    return SendInviteResponse(invite_id=response.status, invite_entity="document")  # Document field invite returns status, not id


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
    # note: entity_type is reused during method execution & could be changed from one type to another (e.g. template > document)
    if entity_type is None:
        entity_type = _detect_entity_type(entity_id, token, client)
    
    created = await _resolve_entity(entity_id, entity_type, name, token, client, ctx)
    entity_id = created.entity_id
    entity_type = created.entity_type

    if entity_type == "document_group":
        group = client.get_document_group(token, entity_id)
        invite_response = _send_document_group_field_invite(client, token, entity_id, orders, group)
    else:
        invite_response = _send_document_field_invite(client, token, entity_id, orders)

    if ctx and created.created_entity_id:
        await ctx.report_progress(progress=3, total=3)

    return SendInviteResponse(
        invite_id=invite_response.invite_id,
        invite_entity=invite_response.invite_entity,
        created_entity_id=created.created_entity_id,
        created_entity_type=created.created_entity_type,
        created_entity_name=created.created_entity_name,
    )
