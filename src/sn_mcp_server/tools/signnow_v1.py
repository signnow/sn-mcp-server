"""
MCP Tool registrations — version 1.0 (v1.0.1 contract surface).

Preserved for backward compatibility. All tools call the same business logic
modules as v2 — only the external parameter schema and response shape differ.

v1.0 tools registered here:
  - send_invite                          (doc/doc_group only, optional JSON orders)
  - create_embedded_invite               (doc/doc_group only, optional JSON orders)
  - create_embedded_sending              (doc/doc_group only, link_expiration in days 14-45)
  - create_embedded_editor               (doc/doc_group only, link_expiration in minutes 15-45)
  - send_invite_from_template            (compound: create + send_invite)
  - create_embedded_sending_from_template (compound: create + embedded sending)
  - create_embedded_editor_from_template  (compound: create + embedded editor)
  - create_embedded_invite_from_template  (compound: create + embedded invite)
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field, TypeAdapter

from sn_mcp_server.token_provider import TokenProvider

from .create_from_template import _create_from_template
from .embedded_editor import _create_embedded_editor
from .embedded_invite import _create_embedded_invite
from .embedded_sending import _create_embedded_sending
from .models import (
    EmbeddedInviteOrder,
    InviteOrder,
)
from .models_v1 import (
    CreateEmbeddedEditorFromTemplateResponse,
    CreateEmbeddedEditorResponseV1,
    CreateEmbeddedInviteFromTemplateResponse,
    CreateEmbeddedInviteResponseV1,
    CreateEmbeddedSendingFromTemplateResponse,
    CreateEmbeddedSendingResponseV1,
    SendInviteFromTemplateResponse,
    SendInviteResponseV1,
)
from .send_invite import _send_invite
from .signnow import _get_token_and_client


def _parse_invite_orders(orders: list[InviteOrder] | str | None) -> list[InviteOrder]:
    """Parse orders from list or JSON string into list[InviteOrder].

    Args:
        orders: List of InviteOrder objects, a JSON string, or None.

    Returns:
        Parsed list of InviteOrder objects; empty list if orders is None.

    Raises:
        ValueError: If JSON string cannot be parsed as list[InviteOrder].
    """
    if orders is None:
        return []
    if isinstance(orders, str):
        try:
            raw: Any = json.loads(orders)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid orders JSON string: {exc}") from exc
        adapter: TypeAdapter[list[InviteOrder]] = TypeAdapter(list[InviteOrder])
        return adapter.validate_python(raw)
    return orders


def _parse_embedded_orders(orders: list[EmbeddedInviteOrder] | str | None) -> list[EmbeddedInviteOrder]:
    """Parse embedded invite orders from list or JSON string into list[EmbeddedInviteOrder].

    Args:
        orders: List of EmbeddedInviteOrder objects, a JSON string, or None.

    Returns:
        Parsed list of EmbeddedInviteOrder objects; empty list if orders is None.

    Raises:
        ValueError: If JSON string cannot be parsed as list[EmbeddedInviteOrder].
    """
    if orders is None:
        return []
    if isinstance(orders, str):
        try:
            raw: Any = json.loads(orders)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid orders JSON string: {exc}") from exc
        adapter: TypeAdapter[list[EmbeddedInviteOrder]] = TypeAdapter(list[EmbeddedInviteOrder])
        return adapter.validate_python(raw)
    return orders


def bind(mcp: Any, cfg: Any) -> None:  # noqa: ANN401
    """Register v1.0 tools on the given FastMCP instance."""
    token_provider = TokenProvider()

    # ─── send_invite v1.0 ────────────────────────────────────────────────────

    @mcp.tool(
        name="send_invite",
        version="1.0",
        description=(
            "Send invite to sign a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have a template or template_group, use the alternative tool: "
            "send_invite_from_template."
        ),
        annotations=ToolAnnotations(
            title="Send signing invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["send_invite", "document", "document_group", "sign", "workflow"],
    )
    async def send_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        orders: Annotated[
            list[InviteOrder] | str | None,
            Field(description="List of orders with recipients (can be a list or JSON string)"),
        ] = None,
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional, auto-detected if not provided)."),
        ] = None,
    ) -> SendInviteResponseV1:
        """Send invite to sign a document or document group (v1.0 contract).

        Args:
            entity_id: ID of the document or document group.
            orders: List of orders with recipients (list or JSON string). Pass empty to raise.
            entity_type: Type of entity (optional, auto-detected if not provided).

        Returns:
            SendInviteResponseV1 with invite_id and invite_entity.
        """
        token, client = _get_token_and_client(token_provider)
        parsed = _parse_invite_orders(orders)
        if not parsed:
            raise ValueError("orders must contain at least one recipient order")
        result = await _send_invite(entity_id, entity_type, parsed, token, client, name=None, ctx=ctx)
        return SendInviteResponseV1(invite_id=result.invite_id, invite_entity=result.invite_entity)

    # ─── create_embedded_invite v1.0 ─────────────────────────────────────────

    @mcp.tool(
        name="create_embedded_invite",
        version="1.0",
        description=(
            "Create embedded invite for signing a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have a template or template_group, use the alternative tool: "
            "create_embedded_invite_from_template."
        ),
        annotations=ToolAnnotations(
            title="Create embedded signing invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["send_invite", "document", "document_group", "sign", "embedded", "workflow"],
    )
    async def create_embedded_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        orders: Annotated[
            list[EmbeddedInviteOrder] | str | None,
            Field(description="List of orders with recipients (can be a list or JSON string)"),
        ] = None,
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional, auto-detected if not provided)."),
        ] = None,
    ) -> CreateEmbeddedInviteResponseV1:
        """Create embedded invite for signing a document or document group (v1.0 contract).

        Args:
            entity_id: ID of the document or document group.
            orders: List of orders with recipients (list or JSON string).
            entity_type: Type of entity (optional, auto-detected if not provided).

        Returns:
            CreateEmbeddedInviteResponseV1 with invite_id, invite_entity, and recipient_links.
        """
        token, client = _get_token_and_client(token_provider)
        parsed = _parse_embedded_orders(orders)
        if not parsed:
            raise ValueError("orders must contain at least one recipient order")
        result = await _create_embedded_invite(entity_id, entity_type, parsed, token, client, name=None, ctx=ctx)
        # Map v2 field to v1 field:
        # - document_group → document_group_invite_id (non-None in this case)
        # - document → first recipient_links entry's document_invite_id
        if result.invite_entity == "document_group":
            invite_id = result.document_group_invite_id or ""
        else:
            first = result.recipient_links[0] if result.recipient_links else {}
            invite_id = first.get("document_invite_id", "")
        return CreateEmbeddedInviteResponseV1(invite_id=invite_id, invite_entity=result.invite_entity, recipient_links=result.recipient_links)

    # ─── create_embedded_sending v1.0 ────────────────────────────────────────

    @mcp.tool(
        name="create_embedded_sending",
        version="1.0",
        description=(
            "Create embedded sending for managing, editing, or sending invites for a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have a template or template_group, use the alternative tool: "
            "create_embedded_sending_from_template."
        ),
        annotations=ToolAnnotations(
            title="Create embedded sending link",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["edit", "document", "document_group", "send_invite", "embedded", "workflow"],
    )
    async def create_embedded_sending(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional, auto-detected if not provided)."),
        ] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration: Annotated[int | None, Field(ge=14, le=45, description="Link expiration in days (14–45)")] = None,
        type: Annotated[Literal["manage", "edit", "send-invite"] | None, Field(description="Type of sending step: 'manage' (default), 'edit', or 'send-invite'")] = "manage",
    ) -> CreateEmbeddedSendingResponseV1:
        """Create embedded sending for a document or document group (v1.0 contract).

        The link_expiration parameter is in days (14–45), matching the v1.0.1 API contract.
        The value is passed as-is to the underlying API field, preserving identical behavior.

        Args:
            entity_id: ID of the document or document group.
            entity_type: Type of entity (optional, auto-detected if not provided).
            redirect_uri: Optional redirect URI after completion.
            redirect_target: Optional redirect target.
            link_expiration: Link expiration in days (14–45).
            type: Sending step type: 'manage', 'edit', or 'send-invite'.

        Returns:
            CreateEmbeddedSendingResponseV1 with sending_entity and sending_url.
        """
        token, client = _get_token_and_client(token_provider)
        # link_expiration (days) is passed as-is to link_expiration_minutes param —
        # the v2 parameter was renamed but still maps to the same API field.
        result = await _create_embedded_sending(entity_id, entity_type, redirect_uri, redirect_target, link_expiration, type, token, client, name=None, ctx=ctx)
        return CreateEmbeddedSendingResponseV1(sending_entity=result.sending_entity, sending_url=result.sending_url)

    # ─── create_embedded_editor v1.0 ─────────────────────────────────────────

    @mcp.tool(
        name="create_embedded_editor",
        version="1.0",
        description=(
            "Create embedded editor for editing a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have a template or template_group, use the alternative tool: "
            "create_embedded_editor_from_template."
        ),
        annotations=ToolAnnotations(
            title="Create embedded editor link",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["edit", "document", "document_group", "embedded"],
    )
    async def create_embedded_editor(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional, auto-detected if not provided)."),
        ] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration: Annotated[int | None, Field(ge=15, le=45, description="Link expiration in minutes (15–45)")] = None,
    ) -> CreateEmbeddedEditorResponseV1:
        """Create embedded editor for a document or document group (v1.0 contract).

        Args:
            entity_id: ID of the document or document group.
            entity_type: Type of entity (optional, auto-detected if not provided).
            redirect_uri: Optional redirect URI after completion.
            redirect_target: Optional redirect target.
            link_expiration: Link expiration in minutes (15–45).

        Returns:
            CreateEmbeddedEditorResponseV1 with editor_entity and editor_url.
        """
        token, client = _get_token_and_client(token_provider)
        result = await _create_embedded_editor(entity_id, entity_type, redirect_uri, redirect_target, link_expiration, token, client, name=None, ctx=ctx)
        return CreateEmbeddedEditorResponseV1(editor_entity=result.editor_entity, editor_url=result.editor_url)

    # ─── send_invite_from_template v1.0 (compound, removed in v2) ────────────

    @mcp.tool(
        name="send_invite_from_template",
        version="1.0",
        description=("Create a document or document group from a template or template group, then send a signing invite immediately. This tool is ONLY for templates and template groups."),
        annotations=ToolAnnotations(
            title="Create from template and send invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "send_invite", "workflow"],
    )
    async def send_invite_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        orders: Annotated[
            list[InviteOrder] | str,
            Field(description="List of orders with recipients for the invite (can be a list or JSON string)"),
        ],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional, auto-detected if not provided)."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
    ) -> SendInviteFromTemplateResponse:
        """Create from template then send invite (v1.0 compound tool).

        Two-step workflow:
        1. Create document/group from template via _create_from_template.
        2. Send invite on the created entity via _send_invite.

        Args:
            entity_id: ID of the template or template group.
            orders: List of orders with recipients (list or JSON string).
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the created document or document group.

        Returns:
            SendInviteFromTemplateResponse with both created entity info and invite details.
        """
        token, client = _get_token_and_client(token_provider)
        parsed = _parse_invite_orders(orders)
        if not parsed:
            raise ValueError("orders must contain at least one recipient order")

        await ctx.report_progress(progress=1, total=3, message="Creating entity from template")
        created = _create_from_template(entity_id, entity_type, name, token, client)

        await ctx.report_progress(progress=2, total=3, message="Sending invite")
        invite = await _send_invite(created.entity_id, created.entity_type, parsed, token, client, name=None, ctx=None)

        await ctx.report_progress(progress=3, total=3, message="Done")
        return SendInviteFromTemplateResponse(
            created_entity_id=created.entity_id,
            created_entity_type=created.entity_type,
            created_entity_name=created.name,
            invite_id=invite.invite_id,
            invite_entity=invite.invite_entity,
        )

    # ─── create_embedded_sending_from_template v1.0 ──────────────────────────

    @mcp.tool(
        name="create_embedded_sending_from_template",
        version="1.0",
        description=("Create a document or document group from a template or template group, then create an embedded sending link immediately. This tool is ONLY for templates and template groups."),
        annotations=ToolAnnotations(
            title="Create from template and embedded sending",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "send_invite", "embedded", "workflow"],
    )
    async def create_embedded_sending_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional, auto-detected if not provided)."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target")] = None,
        link_expiration: Annotated[int | None, Field(ge=14, le=45, description="Link expiration in days (14–45)")] = None,
        type: Annotated[Literal["manage", "edit", "send-invite"] | None, Field(description="Type of sending step: 'manage', 'edit', or 'send-invite'")] = None,
    ) -> CreateEmbeddedSendingFromTemplateResponse:
        """Create from template then create embedded sending (v1.0 compound tool).

        Two-step workflow:
        1. Create document/group from template via _create_from_template.
        2. Create embedded sending on the created entity via _create_embedded_sending.

        The link_expiration parameter is in days (14–45), passed as-is to the
        underlying API field (same field regardless of the v2 parameter rename).

        Args:
            entity_id: ID of the template or template group.
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the created document or document group.
            redirect_uri: Optional redirect URI after completion.
            redirect_target: Optional redirect target.
            link_expiration: Link expiration in days (14–45).
            type: Sending step type: 'manage', 'edit', or 'send-invite'.

        Returns:
            CreateEmbeddedSendingFromTemplateResponse with entity info and sending details.
        """
        token, client = _get_token_and_client(token_provider)

        await ctx.report_progress(progress=1, total=3, message="Creating entity from template")
        created = _create_from_template(entity_id, entity_type, name, token, client)

        await ctx.report_progress(progress=2, total=3, message="Creating embedded sending")
        # link_expiration (days) passed as-is to link_expiration_minutes — same API field.
        sending = await _create_embedded_sending(created.entity_id, created.entity_type, redirect_uri, redirect_target, link_expiration, type, token, client, name=None, ctx=None)

        await ctx.report_progress(progress=3, total=3, message="Done")
        return CreateEmbeddedSendingFromTemplateResponse(
            created_entity_id=created.entity_id,
            created_entity_type=created.entity_type,
            created_entity_name=created.name,
            sending_entity=sending.sending_entity,
            sending_url=sending.sending_url,
        )

    # ─── create_embedded_editor_from_template v1.0 ───────────────────────────

    @mcp.tool(
        name="create_embedded_editor_from_template",
        version="1.0",
        description=("Create a document or document group from a template or template group, then create an embedded editor link immediately. This tool is ONLY for templates and template groups."),
        annotations=ToolAnnotations(
            title="Create from template and embedded editor",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "embedded_editor", "embedded", "workflow"],
    )
    async def create_embedded_editor_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional, auto-detected if not provided)."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target")] = None,
        link_expiration: Annotated[int | None, Field(ge=15, le=45, description="Link expiration in minutes (15–45)")] = None,
    ) -> CreateEmbeddedEditorFromTemplateResponse:
        """Create from template then create embedded editor (v1.0 compound tool).

        Two-step workflow:
        1. Create document/group from template via _create_from_template.
        2. Create embedded editor on the created entity via _create_embedded_editor.

        Args:
            entity_id: ID of the template or template group.
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the created document or document group.
            redirect_uri: Optional redirect URI after completion.
            redirect_target: Optional redirect target.
            link_expiration: Link expiration in minutes (15–45).

        Returns:
            CreateEmbeddedEditorFromTemplateResponse with entity info and editor details.
        """
        token, client = _get_token_and_client(token_provider)

        await ctx.report_progress(progress=1, total=3, message="Creating entity from template")
        created = _create_from_template(entity_id, entity_type, name, token, client)

        await ctx.report_progress(progress=2, total=3, message="Creating embedded editor")
        editor = await _create_embedded_editor(created.entity_id, created.entity_type, redirect_uri, redirect_target, link_expiration, token, client, name=None, ctx=None)

        await ctx.report_progress(progress=3, total=3, message="Done")
        return CreateEmbeddedEditorFromTemplateResponse(
            created_entity_id=created.entity_id,
            created_entity_type=created.entity_type,
            created_entity_name=created.name,
            editor_entity=editor.editor_entity,
            editor_url=editor.editor_url,
        )

    # ─── create_embedded_invite_from_template v1.0 ───────────────────────────

    @mcp.tool(
        name="create_embedded_invite_from_template",
        version="1.0",
        description=("Create a document or document group from a template or template group, then create an embedded signing invite immediately. This tool is ONLY for templates and template groups."),
        annotations=ToolAnnotations(
            title="Create from template and embedded invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "send_invite", "embedded", "workflow"],
    )
    async def create_embedded_invite_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        orders: Annotated[
            list[EmbeddedInviteOrder] | str | None,
            Field(description="List of orders with recipients for the embedded invite (can be a list or JSON string)"),
        ] = None,
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional, auto-detected if not provided)."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
    ) -> CreateEmbeddedInviteFromTemplateResponse:
        """Create from template then create embedded invite (v1.0 compound tool).

        Two-step workflow:
        1. Create document/group from template via _create_from_template.
        2. Create embedded invite on the created entity via _create_embedded_invite.

        Args:
            entity_id: ID of the template or template group.
            orders: List of orders with recipients (list or JSON string).
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the created document or document group.

        Returns:
            CreateEmbeddedInviteFromTemplateResponse with entity info and invite details.
        """
        token, client = _get_token_and_client(token_provider)
        parsed = _parse_embedded_orders(orders)
        if not parsed:
            raise ValueError("orders must contain at least one recipient order")

        await ctx.report_progress(progress=1, total=3, message="Creating entity from template")
        created = _create_from_template(entity_id, entity_type, name, token, client)

        await ctx.report_progress(progress=2, total=3, message="Creating embedded invite")
        invite = await _create_embedded_invite(created.entity_id, created.entity_type, parsed, token, client, name=None, ctx=None)

        await ctx.report_progress(progress=3, total=3, message="Done")
        # Map v2 invite_entity/document_group_invite_id to v1 invite_id field.
        if invite.invite_entity == "document_group":
            invite_id = invite.document_group_invite_id or ""
        else:
            first = invite.recipient_links[0] if invite.recipient_links else {}
            invite_id = first.get("document_invite_id", "")

        return CreateEmbeddedInviteFromTemplateResponse(
            created_entity_id=created.entity_id,
            created_entity_type=created.entity_type,
            created_entity_name=created.name,
            invite_id=invite_id,
            invite_entity=invite.invite_entity,
            recipient_links=invite.recipient_links,
        )
