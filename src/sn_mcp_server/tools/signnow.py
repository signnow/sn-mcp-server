import asyncio
import pathlib
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastmcp import Context
from fastmcp.resources import ResourceContent, ResourceResult
from fastmcp.server.dependencies import get_http_headers
from mcp.types import ToolAnnotations
from pydantic import Field

from signnow_client import SignNowAPIClient

from ..token_provider import TokenProvider
from .cancel_invite import _cancel_invite
from .create_from_template import _create_from_template
from .create_template import create_template as _create_template
from .document import _get_document, _update_document_fields, _upload_document
from .document_download_link import _get_document_download_link
from .document_view import _VIEWER_HTML, VIEWER_RESOURCE_URI, _view_document
from .embedded_editor import (
    _create_embedded_editor,
)
from .embedded_invite import (
    _create_embedded_invite,
)
from .embedded_sending import (
    _SENDER_HTML,
    SENDER_RESOURCE_URI,
    _create_embedded_sending,
)
from .invite_status import _get_invite_status
from .list_contacts import _list_contacts
from .list_documents import _list_document_groups
from .list_templates import _list_all_templates
from .models import (
    CancelInviteResponse,
    ContactListResponse,
    CreateEmbeddedEditorResponse,
    CreateEmbeddedInviteResponse,
    CreateEmbeddedSendingResponse,
    CreateFromTemplateResponse,
    CreateTemplateResult,
    DocumentDownloadLinkResponse,
    DocumentGroup,
    EmbeddedInviteOrder,
    InviteOrder,
    InviteStatus,
    SendInviteResponse,
    SendReminderResponse,
    SigningLinkResponse,
    SimplifiedDocumentGroupsResponse,
    TemplateSummaryList,
    UpdateDocumentFields,
    UpdateDocumentFieldsResponse,
    UpdateInviteRecipientResponse,
    UploadDocumentResponse,
    ViewDocumentResponse,
)
from .reminder import _send_invite_reminder
from .send_invite import _send_invite
from .signing_link import _get_signing_link
from .update_invite_recipient import _update_invite_recipient

RESOURCE_PREFERRED_SUFFIX = "\n\nPreferred: use this as an MCP Resource (resources/read) when your client supports resources."

TOOL_FALLBACK_SUFFIX = "\n\nNote: If your client supports MCP Resources, prefer the resource version of this endpoint; this tool exists as a compatibility fallback for tool-only clients."


def _get_token_and_client(token_provider: TokenProvider) -> tuple[str, SignNowAPIClient]:
    """Get access token and initialize SignNow API client.

    Args:
        token_provider: TokenProvider instance to get access token

    Returns:
        Tuple of (access_token, SignNowAPIClient instance)

    Raises:
        ValueError: If no access token is available
    """
    headers = get_http_headers(include={"authorization"})
    token = token_provider.get_access_token(headers)

    if not token:
        raise ValueError("No access token available")

    client = SignNowAPIClient(token_provider.signnow_config)
    return token, client


def bind(mcp: Any, cfg: Any) -> None:  # noqa: ANN401
    # Initialize token provider
    token_provider = TokenProvider()

    async def _list_all_templates_impl(ctx: Context, limit: int = 50, offset: int = 0) -> TemplateSummaryList:
        token, client = _get_token_and_client(token_provider)
        return await _list_all_templates(ctx, token, client, limit=limit, offset=offset)

    @mcp.tool(
        name="list_all_templates",
        description="Get simplified list of all templates and template groups with basic information" + TOOL_FALLBACK_SUFFIX,
        annotations=ToolAnnotations(
            title="List templates and template groups",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "list"],
    )
    async def list_all_templates(
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of items to return (1-100, default 50)"),
        ] = 50,
        offset: Annotated[
            int,
            Field(ge=0, description="Number of items to skip for pagination (default 0)"),
        ] = 0,
    ) -> TemplateSummaryList:
        """Get all templates and template groups from all folders.

        This tool combines both individual templates and template groups into a single response.
        Individual templates are marked with entity_type='template' and template groups with entity_type='template_group'.
        Supports pagination via limit/offset parameters.

        Note: Individual templates are deprecated. For new implementations, prefer using template groups
        which are more feature-rich and actively maintained.

        Args:
            limit: Maximum number of items to return (1-100, default 50)
            offset: Number of items to skip for pagination (default 0)
        """
        return await _list_all_templates_impl(ctx, limit=limit, offset=offset)

    @mcp.resource(
        "signnow://templates{?limit,offset}",
        name="list_all_templates_resource",
        description="Get simplified list of all templates and template groups with basic information" + RESOURCE_PREFERRED_SUFFIX,
        tags=["template", "template_group", "list"],
    )
    async def list_all_templates_resource(
        ctx: Context,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of items to return (1-100, default 50)"),
        ] = 50,
        offset: Annotated[
            int,
            Field(ge=0, description="Number of items to skip for pagination (default 0)"),
        ] = 0,
    ) -> TemplateSummaryList:
        return await _list_all_templates_impl(ctx, limit=limit, offset=offset)

    async def _list_documents_impl(
        ctx: Context,
        filter: Literal["signed", "pending", "waiting-for-me", "waiting-for-others", "unsent"] | None = None,
        sortby: Literal["updated", "created", "document-name"] | None = None,
        order: Literal["asc", "desc"] | None = None,
        folder_id: str | None = None,
        expired_filter: Literal["all", "expired", "not-expired"] = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> SimplifiedDocumentGroupsResponse:
        if order is not None and sortby is None:
            raise ValueError("order can be used only with sortby")
        token, client = _get_token_and_client(token_provider)
        return await _list_document_groups(
            ctx,
            token,
            client,
            filter=filter,
            sortby=sortby,
            order=order,
            folder_id=folder_id,
            expired_filter=expired_filter,
            limit=limit,
            offset=offset,
        )

    @mcp.tool(
        name="list_documents",
        description=(
            "Get simplified list of documents and document groups with basic information. "
            "Returns both documents and document groups in a unified format. "
            "Use this tool to fetch lists of documents by status, e.g. "
            "documents waiting for your signature (waiting-for-me) or expired documents "
            "(expired_filter=expired). " + TOOL_FALLBACK_SUFFIX
        ),
        annotations=ToolAnnotations(
            title="List documents and document groups",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["document", "document_group", "list"],
    )
    async def list_documents(
        ctx: Context,
        filter: Annotated[
            Literal["signed", "pending", "waiting-for-me", "waiting-for-others", "unsent"] | None,
            Field(description=("Filter by document group status (optional). Available values: signed, pending, waiting-for-me, waiting-for-others, unsent.")),
        ] = None,
        sortby: Annotated[
            Literal["updated", "created", "document-name"] | None,
            Field(description=("Sort by created date, updated date, or document name (optional). Available values: updated, created, document-name.")),
        ] = None,
        order: Annotated[
            Literal["asc", "desc"] | None,
            Field(description=("Order of sorting (optional, can be used only with sortby). Available values: asc, desc.")),
        ] = None,
        folder_id: Annotated[str | None, Field(description="Filter by folder ID (optional)")] = None,
        expired_filter: Annotated[
            Literal["all", "expired", "not-expired"],
            Field(description=("Filter by invite expiredness (optional, default: all). Available values: all, expired, not-expired.")),
        ] = "all",
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of items to return (1-100, default 50)"),
        ] = 50,
        offset: Annotated[
            int,
            Field(ge=0, description="Number of items to skip for pagination (default 0)"),
        ] = 0,
    ) -> SimplifiedDocumentGroupsResponse:
        """Provide simplified list of documents and document groups with basic fields.

        This tool retrieves both individual documents and document groups from SignNow,
        presenting them all in a unified format. If you need a list of documents or
        a list of document groups, this is the right tool to use.
        You can also use it to fetch specific lists like documents waiting for your
        signature (waiting-for-me) or expired documents (expired_filter=expired).
        Supports pagination via limit/offset parameters.

        Args:
            filter: Filter by document group status (optional)
            sortby: Sort by created date, updated date, or document name (optional)
            order: Order of sorting (optional, requires sortby)
            folder_id: Filter by folder ID (optional)
            expired_filter: Filter by invite expiredness (optional, default: all)
            limit: Maximum number of items to return (1-100, default 50)
            offset: Number of items to skip for pagination (default 0)
        """
        return await _list_documents_impl(
            ctx,
            filter=filter,
            sortby=sortby,
            order=order,
            folder_id=folder_id,
            expired_filter=expired_filter,
            limit=limit,
            offset=offset,
        )

    @mcp.resource(
        "signnow://documents/{?filter,sortby,order,folder_id,expired_filter,limit,offset}",
        name="list_documents_resource",
        description=(
            "Get simplified list of documents and document groups with basic information. "
            "Returns both documents and document groups in a unified format. "
            "Use this resource to fetch lists of documents by status, e.g. "
            "documents waiting for your signature (waiting-for-me) or expired documents "
            "(expired_filter=expired). " + RESOURCE_PREFERRED_SUFFIX
        ),
        tags=["document", "document_group", "list"],
        mime_type="application/json",
    )
    async def list_documents_resource(
        ctx: Context,
        filter: Annotated[
            Literal["signed", "pending", "waiting-for-me", "waiting-for-others", "unsent"] | None,
            Field(description=("Filter by document group status (optional). Available values: signed, pending, waiting-for-me, waiting-for-others, unsent.")),
        ] = None,
        sortby: Annotated[
            Literal["updated", "created", "document-name"] | None,
            Field(description=("Sort by created date, updated date, or document name (optional). Available values: updated, created, document-name.")),
        ] = None,
        order: Annotated[
            Literal["asc", "desc"] | None,
            Field(description=("Order of sorting (optional, can be used only with sortby). Available values: asc, desc.")),
        ] = None,
        folder_id: Annotated[str | None, Field(description="Filter by folder ID (optional)")] = None,
        expired_filter: Annotated[
            Literal["all", "expired", "not-expired"],
            Field(description=("Filter by invite expiredness (optional, default: all). Available values: all, expired, not-expired.")),
        ] = "all",
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of items to return (1-100, default 50)"),
        ] = 50,
        offset: Annotated[
            int,
            Field(ge=0, description="Number of items to skip for pagination (default 0)"),
        ] = 0,
    ) -> SimplifiedDocumentGroupsResponse:
        return await _list_documents_impl(
            ctx,
            filter=filter,
            sortby=sortby,
            order=order,
            folder_id=folder_id,
            expired_filter=expired_filter,
            limit=limit,
            offset=offset,
        )

    @mcp.tool(
        name="send_invite",
        description=(
            "Send invite to sign a document, document group, template, or template group. "
            "Supports both field invites (documents with roles/fields) and freeform invites "
            "(documents without fields). Document type is auto-detected — omit 'role' for "
            "freeform documents. For templates and template groups, automatically creates a "
            "document/group first, then sends the invite. "
            "Set self_sign=True (and omit orders) to sign the document yourself — the tool "
            "resolves the current user's email and populates SendInviteResponse.link with a "
            "direct signing link. The 'link' field is also populated when a freeform "
            "recipient's email matches the authenticated user's primary email."
        ),
        annotations=ToolAnnotations(
            title="Send signing invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["send_invite", "document", "document_group", "template", "template_group", "sign", "workflow"],
    )
    async def send_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document, document group, template, or template group")],
        orders: Annotated[
            list[InviteOrder] | None,
            Field(
                description=("List of orders with recipients. Required unless self_sign=True. When self_sign=True, omit orders — the tool fills in the current user as the sole recipient."),
                examples=[
                    [{"order": 1, "recipients": [{"email": "user@example.com", "role": "Signer 1", "action": "sign"}]}],
                    [{"order": 1, "recipients": [{"email": "signer@example.com", "action": "sign"}]}],
                ],
            ),
        ] = None,
        preview_was_shown: Annotated[
            bool | None,
            Field(
                description=(
                    "This flag signals that the user has viewed the document preview. "
                    "Prompt the user to view the document before submitting. "
                    "If the user says yes, call view_document first, show the result, then call send_invite again with preview_was_shown=True. "
                    "If the user says no, call send_invite with preview_was_shown=False."
                )
            ),
        ] = None,
        entity_type: Annotated[
            Literal["document", "document_group", "template", "template_group"] | None,
            Field(description="Type of entity: 'document', 'document_group', 'template', or 'template_group' (optional). Auto-detected if not provided."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group (used only when entity_type is template or template_group)")] = None,
        self_sign: Annotated[
            bool,
            Field(
                description=(
                    "If True, the tool resolves the current user's primary email server-side and "
                    "sends a freeform invite to the user themselves. The response's 'link' field "
                    "is populated with a direct signing link. Must be combined with an empty/omitted "
                    "orders. Requires a field-less document or document group — for entities with "
                    "fields/roles, use create_embedded_sending instead."
                )
            ),
        ] = False,
    ) -> SendInviteResponse:
        """Send invite to sign a document, document group, template, or template group.

        When entity_type is 'template' or 'template_group', this tool automatically:
        1. Creates a document/group from the template (create_from_template)
        2. Sends an invite to the created entity

        For direct document/document_group calls the invite is sent immediately.
        The entity type is auto-detected if not provided.

        Note: If the document has no fields, a freeform invite is sent automatically.
        In that case, ``role`` on each recipient is optional and ignored. For document
        groups, role presence is checked per document — if no documents have roles,
        a freeform group invite is sent instead.

        When sender and recipient emails match, SendInviteResponse.link is populated
        with a direct signing link so the sender can sign without checking their inbox.

        Self-sign shortcut: pass ``self_sign=True`` (and omit ``orders``) to sign the
        document yourself. The tool resolves your primary email, sends a freeform
        invite with you as the sole recipient, and returns a SendInviteResponse whose
        ``link`` field holds a ready-to-open signing link. Only valid for field-less
        documents/groups — field entities should use create_embedded_sending.

        Args:
            entity_id: ID of the document, document group, template, or template group
            orders: List of orders with recipients. Required unless self_sign=True.
            preview_was_shown: Prompt the user to view the document first. True if shown, False to skip.
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the new document or document group (template flows only)
            self_sign: If True, self-sign the document using the current user's email.

        Returns:
            SendInviteResponse with invite details. ``link`` is populated when
            self-signing or when recipient email equals the sender's email.
        """
        token, client = _get_token_and_client(token_provider)

        if self_sign:
            if orders:
                raise ValueError("orders must be empty when self_sign=True — the tool fills in the current user as the sole recipient")
        else:
            if not orders:
                raise ValueError("orders must contain at least one recipient order")

        return await _send_invite(entity_id, entity_type, orders or [], token, client, name, ctx, self_sign=self_sign)

    @mcp.tool(
        name="create_embedded_invite",
        description=(
            "Create embedded invite for signing a document, document group, template, or template group. "
            "For templates and template groups, automatically creates a document/group first, then creates the embedded invite."
        ),
        annotations=ToolAnnotations(
            title="Create embedded signing invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["send_invite", "document", "document_group", "template", "template_group", "sign", "embedded", "workflow"],
    )
    async def create_embedded_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document, document group, template, or template group")],
        orders: Annotated[
            list[EmbeddedInviteOrder],
            Field(
                description="List of orders with recipients.",
                examples=[
                    [{"order": 1, "recipients": [{"email": "user@example.com", "role": "Signer 1", "action": "sign", "auth_method": "none"}]}],
                ],
            ),
        ],
        entity_type: Annotated[
            Literal["document", "document_group", "template", "template_group"] | None,
            Field(description="Type of entity: 'document', 'document_group', 'template', or 'template_group' (optional). Auto-detected if not provided."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group (used only when entity_type is template or template_group)")] = None,
    ) -> CreateEmbeddedInviteResponse:
        """Create embedded invite for signing a document, document group, template, or template group.

        When entity_type is 'template' or 'template_group', this tool automatically:
        1. Creates a document/group from the template (create_from_template)
        2. Creates an embedded invite for the created entity

        For direct document/document_group calls the invite is created immediately.
        The entity type is auto-detected if not provided.

        Args:
            entity_id: ID of the document, document group, template, or template group
            orders: List of orders with recipients.
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the new document or document group (template flows only)

        Returns:
            CreateEmbeddedInviteResponse with invite details; created_entity_* fields populated for template flows
        """
        token, client = _get_token_and_client(token_provider)

        if not orders:
            raise ValueError("orders must contain at least one recipient order")

        return await _create_embedded_invite(entity_id, entity_type, orders, token, client, name, ctx)

    @mcp.tool(
        name="create_embedded_sending",
        description=(
            "Create embedded sending for managing, editing, or sending invites for a document, document group, template, or template group. "
            "For templates and template groups, automatically creates a document/group first, then creates the embedded sending. "
            "In MCP Apps-compatible clients the sender UI renders inline — no tab switch needed."
        ),
        meta={"ui": {"resourceUri": SENDER_RESOURCE_URI}},
        annotations=ToolAnnotations(
            title="Create embedded sending link",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["edit", "document", "document_group", "template", "template_group", "send_invite", "embedded", "workflow"],
    )
    async def create_embedded_sending(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document, document group, template, or template group")],
        entity_type: Annotated[
            Literal["document", "document_group", "template", "template_group"] | None,
            Field(description="Type of entity: 'document', 'document_group', 'template', or 'template_group' (optional). Auto-detected if not provided."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group (used only when entity_type is template or template_group)")] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration_minutes: Annotated[int | None, Field(ge=15, le=45, description="Link lifetime in minutes (15–45). Default: 15 min.")] = None,
        type: Annotated[Literal["manage", "edit", "send-invite"] | None, Field(description="Type of sending step: 'manage', 'edit', or 'send-invite'")] = "manage",
    ) -> CreateEmbeddedSendingResponse:
        """Create embedded sending for managing, editing, or sending invites for a document, document group, template, or template group.

        When entity_type is 'template' or 'template_group', this tool automatically:
        1. Creates a document/group from the template (create_from_template)
        2. Creates an embedded sending for the created entity

        For direct document/document_group calls the sending is created immediately.
        The entity type is auto-detected if not provided.

        Args:
            entity_id: ID of the document, document group, template, or template group
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the new document or document group (template flows only)
            redirect_uri: Optional redirect URI for the sending link
            redirect_target: Optional redirect target for the sending link
            link_expiration_minutes: Link lifetime in minutes (15–45). Default: 15 min.
            type: Specifies the sending step: 'manage' (default), 'edit', 'send-invite'

        Returns:
            CreateEmbeddedSendingResponse with sending details; created_entity_* fields populated for template flows
        """
        token, client = _get_token_and_client(token_provider)

        return await _create_embedded_sending(entity_id, entity_type, redirect_uri, redirect_target, link_expiration_minutes, type, token, client, name, ctx)

    @mcp.tool(
        name="create_embedded_editor",
        description=(
            "Create embedded editor for editing a document, document group, template, or template group. "
            "For templates and template groups, automatically creates a document/group first, then creates the embedded editor."
        ),
        annotations=ToolAnnotations(
            title="Create embedded editor link",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["edit", "document", "document_group", "template", "template_group", "embedded", "workflow"],
    )
    async def create_embedded_editor(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document, document group, template, or template group")],
        entity_type: Annotated[
            Literal["document", "document_group", "template", "template_group"] | None,
            Field(description="Type of entity: 'document', 'document_group', 'template', or 'template_group' (optional). Auto-detected if not provided."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group (used only when entity_type is template or template_group)")] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration_minutes: Annotated[int | None, Field(ge=15, le=43200, description="Link lifetime in minutes (15–43200). Default: 15 min.")] = None,
    ) -> CreateEmbeddedEditorResponse:
        """Create embedded editor for editing a document, document group, template, or template group.

        When entity_type is 'template' or 'template_group', this tool automatically:
        1. Creates a document/group from the template (create_from_template)
        2. Creates an embedded editor for the created entity

        For direct document/document_group calls the editor is created immediately.
        The entity type is auto-detected if not provided.

        Args:
            entity_id: ID of the document, document group, template, or template group
            entity_type: Type of entity (optional, auto-detected if not provided).
            name: Optional name for the new document or document group (template flows only)
            redirect_uri: Optional redirect URI for the editor link
            redirect_target: Optional redirect target for the editor link
            link_expiration_minutes: Link lifetime in minutes (15–43200). Default: 15 min.

        Returns:
            CreateEmbeddedEditorResponse with editor details; created_entity_* fields populated for template flows
        """
        token, client = _get_token_and_client(token_provider)

        return await _create_embedded_editor(entity_id, entity_type, redirect_uri, redirect_target, link_expiration_minutes, token, client, name, ctx)

    @mcp.tool(
        name="create_template",
        description="Convert an existing document or document group into a reusable template",
        annotations=ToolAnnotations(
            title="Create template from document or document group",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "document", "document_group", "create", "workflow"],
    )
    def create_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group to convert into a template")],
        template_name: Annotated[str, Field(description="Name for the new template")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group'. Omit to auto-detect (tries document_group first, then document). Pass explicitly to save one API call."),
        ] = None,
    ) -> CreateTemplateResult:
        """Convert an existing document or document group into a reusable template.

        Call this when no suitable template yet exists and the user wants to send their
        document for signing. After creation, use the returned template_id with
        send_invite_from_template or create_embedded_sending_from_template.

        If entity_type is omitted, auto-detects: tries document_group first, then document.
        Pass entity_type explicitly when you already know the type to save one API call.

        For document groups, template creation is asynchronous — template_id will be None.
        Use list_all_templates after a short delay to retrieve the ID.

        Args:
            entity_id: ID of the document or document group to templatize.
            template_name: Name for the new template.
            entity_type: Optional. 'document' | 'document_group' | None (auto-detect).

        Returns:
            CreateTemplateResult with template_id (None for async doc group path),
            template_name, and entity_type.
        """
        token, client = _get_token_and_client(token_provider)
        return _create_template(client, token, entity_id, template_name, entity_type)

    @mcp.tool(
        name="create_from_template",
        description="Create a new document or document group from an existing template or template group",
        annotations=ToolAnnotations(
            title="Create from template",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "document", "document_group", "create", "workflow"],
    )
    def create_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document group or document (required for template groups)")] = None,
    ) -> CreateFromTemplateResponse:
        """Create a new document or document group from an existing template or template group.

        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            name: Optional name for the new document group or document (required for template groups)

        Returns:
            CreateFromTemplateResponse with created entity ID, type and name
        """
        token, client = _get_token_and_client(token_provider)

        return _create_from_template(entity_id, entity_type, name, token, client)

    def _get_invite_status_impl(ctx: Context, entity_id: str, entity_type: Literal["document", "document_group"] | None) -> InviteStatus:
        token, client = _get_token_and_client(token_provider)
        return _get_invite_status(entity_id, entity_type, token, client)

    @mcp.tool(
        name="get_invite_status",
        description=(
            "Get invite status for a document or document group. "
            "Supports field invites and freeform invites (field invite is preferred when both exist). "
            "For freeform document groups, uses the group documents list so signature_requests include signer emails when the API provides them. "
            "Returns invite_mode 'field' or 'freeform'."
        )
        + TOOL_FALLBACK_SUFFIX,
        annotations=ToolAnnotations(
            title="Get invite status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["invite", "status", "document", "document_group", "workflow"],
    )
    def get_invite_status(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> InviteStatus:
        return _get_invite_status_impl(ctx, entity_id, entity_type)

    @mcp.resource(
        "signnow://invite-status/{entity_id}{?entity_type}",
        name="get_invite_status_resource",
        description=("Get invite status for a document or document group (field and freeform). See get_invite_status tool for behaviour.") + RESOURCE_PREFERRED_SUFFIX,
        tags=["invite", "status", "document", "document_group", "workflow"],
    )
    def get_invite_status_resource(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> InviteStatus:
        return _get_invite_status_impl(ctx, entity_id, entity_type)

    def _get_document_download_link_impl(ctx: Context, entity_id: str, entity_type: Literal["document", "document_group"] | None) -> DocumentDownloadLinkResponse:
        token, client = _get_token_and_client(token_provider)

        # Initialize client and use the imported function from document_download_link module
        return _get_document_download_link(entity_id, entity_type, token, client)

    @mcp.tool(
        name="get_document_download_link",
        description="Get download link for a document or document group" + TOOL_FALLBACK_SUFFIX,
        annotations=ToolAnnotations(
            title="Get document download link",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["document", "document_group", "download", "link"],
    )
    def get_document_download_link(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> DocumentDownloadLinkResponse:
        """Get download link for a document or document group.

        For documents: Returns direct download link.
        For document groups: Merges all documents in the group and returns download link for the merged document.

        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.

        Returns:
            DocumentDownloadLinkResponse with download link
        """
        return _get_document_download_link_impl(ctx, entity_id, entity_type)

    @mcp.resource(
        "signnow://document-download-link/{entity_id}{?entity_type}",
        name="get_document_download_link_resource",
        description="Get download link for a document or document group" + RESOURCE_PREFERRED_SUFFIX,
        tags=["document", "document_group", "download", "link"],
    )
    def get_document_download_link_resource(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> DocumentDownloadLinkResponse:
        return _get_document_download_link_impl(ctx, entity_id, entity_type)

    def _get_signing_link_impl(ctx: Context, entity_id: str, entity_type: Literal["document", "document_group"] | None) -> SigningLinkResponse:
        token, client = _get_token_and_client(token_provider)

        # Initialize client and use the imported function from signing_link module
        return _get_signing_link(entity_id, entity_type, token, client)

    @mcp.tool(
        name="get_signing_link",
        description="Get signing link for a document or document group" + TOOL_FALLBACK_SUFFIX,
        annotations=ToolAnnotations(
            title="Get signing link",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["document", "document_group", "sign", "link"],
    )
    def get_signing_link(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> SigningLinkResponse:
        """Get signing link for a document or document group.

        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.

        Returns:
            SigningLinkResponse with signing link
        """
        return _get_signing_link_impl(ctx, entity_id, entity_type)

    @mcp.resource(
        "signnow://signing-link/{entity_id}{?entity_type}",
        name="get_signing_link_resource",
        description="Get signing link for a document or document group" + RESOURCE_PREFERRED_SUFFIX,
        tags=["document", "document_group", "sign", "link"],
    )
    def get_signing_link_resource(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> SigningLinkResponse:
        return _get_signing_link_impl(ctx, entity_id, entity_type)

    def _get_document_impl(ctx: Context, entity_id: str, entity_type: Literal["document", "document_group", "template", "template_group"] | None) -> DocumentGroup:
        token, client = _get_token_and_client(token_provider)

        # Initialize client and use the imported function from document module
        return _get_document(client, token, entity_id, entity_type)

    @mcp.tool(
        name="get_document",
        description="Get full document, template, template group or document group information with field values",
        annotations=ToolAnnotations(
            title="Get document or group details",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["document", "document_group", "template", "template_group", "get", "fields"],
    )
    def get_document(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document, template, template group or document group to retrieve")],
        entity_type: Annotated[
            Literal["document", "document_group", "template", "template_group"] | None,
            Field(description="Type of entity: 'document', 'template', 'template_group' or 'document_group' (optional). If not provided, will be determined automatically"),
        ] = None,
    ) -> DocumentGroup:
        """Get full document, template, template group or document group information with field values.

        Always returns a unified DocumentGroup wrapper even for a single document.

        This tool retrieves complete information about a document, template, template group or document group,
        including all field values, roles, and metadata. If entity_type is not provided,
        the tool will automatically determine whether the entity is a document, template, template group or document group.

        For documents, returns a DocumentGroup with a single document.
        For templates, returns a DocumentGroup with a single template.
        For template groups, returns a DocumentGroup with all templates in the group.
        For document groups, returns a DocumentGroup with all documents in the group.

        Args:
            entity_id: ID of the document, template, template group or document group to retrieve
            entity_type: Type of entity: 'document', 'template', 'template_group' or 'document_group' (optional)

        Returns:
            DocumentGroup with complete information including field values for all documents
        """
        return _get_document_impl(ctx, entity_id, entity_type)

    @mcp.resource(
        "signnow://document/{entity_id}{?entity_type}",
        name="get_document_resource",
        description="Get full document, template, template group or document group information with field values" + RESOURCE_PREFERRED_SUFFIX,
        tags=["document", "document_group", "template", "template_group", "get", "fields"],
    )
    def get_document_resource(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document, template, template group or document group to retrieve")],
        entity_type: Annotated[
            Literal["document", "document_group", "template", "template_group"] | None,
            Field(description="Type of entity: 'document', 'template', 'template_group' or 'document_group' (optional). If not provided, will be determined automatically"),
        ] = None,
    ) -> DocumentGroup:
        return _get_document_impl(ctx, entity_id, entity_type)

    @mcp.tool(
        name="update_document_fields",
        description="Update text fields in multiple documents (only individual documents, not document groups)",
        annotations=ToolAnnotations(
            title="Update document text fields",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["document", "fields", "update", "prefill"],
    )
    def update_document_fields(
        ctx: Context,
        update_requests: Annotated[
            list[UpdateDocumentFields],
            Field(
                description="Array of document field update requests",
                examples=[
                    [
                        {
                            "document_id": "abc123",
                            "fields": [
                                {"name": "FieldName1", "value": "New Value 1"},
                                {"name": "FieldName2", "value": "New Value 2"},
                            ],
                        },
                        {
                            "document_id": "def456",
                            "fields": [{"name": "FieldName3", "value": "New Value 3"}],
                        },
                    ],
                ],
            ),
        ],
    ) -> UpdateDocumentFieldsResponse:
        """Update text fields in multiple documents.

        This tool updates text fields in multiple documents using the SignNow API.
        Only text fields can be updated using the prefill_text_fields endpoint.

        IMPORTANT: This tool works only with individual documents, not document groups.
        To find out what fields are available in a document or document group,
        use the get_document tool first.

        Args:
            update_requests: Array of UpdateDocumentFields with document IDs and fields to update

        Returns:
            UpdateDocumentFieldsResponse with results for each document update
        """
        token, client = _get_token_and_client(token_provider)

        # Initialize client and use the imported function from document module
        return _update_document_fields(client, token, update_requests)

    @mcp.tool(
        name="upload_document",
        description=(
            "Upload a document to SignNow from a local file path, public URL, or MCP resource attachment. "
            "Supported file types: PDF, DOC, DOCX, PNG, JPG, JPEG. Max file size: 40 MB. "
            "On success the response includes a 'next_steps' array (prepare invite / send for signing / self-sign) "
            "and an 'agent_guidance' string — present those options to the user and wait for them to choose "
            "before calling any follow-up tool. "
            "NOTE: For URL uploads, the returned filename is locally inferred and may differ from "
            "how SignNow names the document."
        ),
        annotations=ToolAnnotations(
            title="Upload document",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["document", "upload", "file"],
    )
    async def upload_document(
        ctx: Context,
        resource_uri: Annotated[
            str | None,
            Field(
                description=("MCP resource URI of an attached file (preferred when your client supports resource attachments). Provide exactly one of resource_uri, file_path, or file_url."),
            ),
        ] = None,
        file_path: Annotated[
            str | None,
            Field(
                description=(
                    "Absolute or ~-relative path to a local file to upload. "
                    "The resolved path must be within the safe upload base directory "
                    "(SAFE_UPLOAD_BASE, defaulting to your home directory); "
                    "paths outside that base (e.g. /tmp/foo.pdf) will be rejected. "
                    "Supported: .pdf, .doc, .docx, .png, .jpg, .jpeg. "
                    "Provide exactly one of resource_uri, file_path, or file_url."
                ),
            ),
        ] = None,
        file_url: Annotated[
            str | None,
            Field(
                description=("Publicly accessible URL to the file to upload. SignNow will fetch the file from this URL. Provide exactly one of resource_uri, file_path, or file_url."),
            ),
        ] = None,
        filename: Annotated[
            str | None,
            Field(
                description=(
                    "Optional custom name for the document as it will appear in SignNow. "
                    "If omitted, the name is derived from the file path, URL, or resource URI. "
                    "Required when using resource_uri and the filename cannot be inferred."
                ),
            ),
        ] = None,
    ) -> UploadDocumentResponse:
        """Upload a document to SignNow.

        Provide exactly one of: resource_uri, file_path, or file_url.
        Supported formats: PDF, DOC, DOCX, PNG, JPG, JPEG. Max file size: 40 MB.

        Preferred source order:
        1. resource_uri — if the user @-attached a file in their MCP client
        2. file_path — if the user provided a local path
        3. file_url — if the user provided a public URL

        After upload, load the 'signnow101' skill for guidance on next steps.
        Primary suggestions (present in this order):
        1. Prepare a role-based invite (create_embedded_sending)
        2. Send for signing as a freeform invite (send_invite with recipient email)
        3. Sign the document yourself (send_invite with self_sign=True)

        Secondary suggestion (only if the user hints at reuse):
        - Turn the document into a reusable template (create_embedded_editor)

        Args:
            ctx: FastMCP context (injected)
            resource_uri: MCP resource URI from an attached file
            file_path: Local file path (absolute or ~-relative)
            file_url: Public URL to the file
            filename: Optional custom document name in SignNow
        """
        token, client = _get_token_and_client(token_provider)

        # Validate mutually-exclusive source inputs before any I/O
        provided = sum(x is not None for x in (resource_uri, file_path, file_url))
        if provided > 1:
            raise ValueError("Provide exactly one of resource_uri, file_path, or file_url — not multiple")
        if provided == 0:
            raise ValueError("Provide one of: resource_uri, file_path, or file_url")

        resource_bytes: bytes | None = None
        if resource_uri is not None:
            # L-5: Validate resource_uri is not empty/whitespace
            if not resource_uri.strip():
                raise ValueError("resource_uri must not be empty. Provide a valid MCP resource URI.")
            result: ResourceResult = await ctx.read_resource(resource_uri)
            # H-1: Guard against empty contents list
            if not result.contents:
                raise ValueError(f"Resource at {resource_uri!r} returned no content. Ensure the URI points to a valid binary file.")
            first: ResourceContent = result.contents[0]
            if not isinstance(first.content, bytes):
                raise ValueError(f"Resource at {resource_uri} returned text, expected binary file content. Ensure the resource provides raw file bytes.")
            resource_bytes = first.content
            if filename is None:
                parsed_name = pathlib.PurePosixPath(urlparse(str(resource_uri)).path).name
                # M-5: Raise explicit error when filename cannot be inferred from URI
                if not parsed_name:
                    raise ValueError(f"Cannot infer filename from resource URI {resource_uri!r}. Provide the 'filename' parameter explicitly.")
                filename = parsed_name

        # H-3: Run synchronous _upload_document off the async event loop
        return await asyncio.to_thread(
            _upload_document,
            client=client,
            token=token,
            resource_bytes=resource_bytes,
            file_path=file_path,
            file_url=file_url,
            filename=filename,
        )

    @mcp.tool(
        name="send_invite_reminder",
        description=("Send a signing reminder to pending signers on a document or document group. "),
        annotations=ToolAnnotations(
            title="Send signing reminder",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["send_invite", "reminder", "document", "document_group", "workflow"],
    )
    async def send_invite_reminder(
        ctx: Context,
        entity_id: Annotated[str, Field(description="Document ID or document group ID")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description=("Entity type: 'document' or 'document_group'. Auto-detected if omitted (document_group tried first). Pass explicitly to avoid an extra auto-detection GET.")),
        ] = None,
        email: Annotated[
            str | None,
            Field(
                description="Remind only this specific recipient. If omitted, all pending signers are reminded.",
                pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            ),
        ] = None,
        subject: Annotated[str | None, Field(description="Custom email subject for the reminder.")] = None,
        message: Annotated[str | None, Field(description="Custom message body for the reminder.")] = None,
    ) -> SendReminderResponse:
        """Send a signing reminder to pending signers on a document or document group.

        Auto-detects entity type by trying GET /documentgroup/{id} (v2) first (modern),
        then GET /document/{id} as legacy fallback. Non-404 errors propagate immediately.

        For documents: sends a copy via POST /document/{id}/email2 to each pending signer.
        For document groups: uses POST /v2/document-groups/{id}/send-email to notify all
        pending signers across all documents in the group.

        Skips signers whose invite is already completed or cancelled (reported in 'skipped').
        API failures are reported in 'failed' and can be retried.

        Tip: if entity_type is known, pass it explicitly to avoid an extra auto-detection GET.
        Tip: use list_documents first to discover document IDs by name or criteria.

        Args:
            entity_id: Document ID or document group ID.
            entity_type: Optional discriminator ('document' or 'document_group').
            email: Optional — target a single recipient.
            subject: Optional custom email subject.
            message: Optional custom message body.

        Returns:
            SendReminderResponse with entity_id, entity_type, recipients_reminded, skipped, failed.
        """
        token, client = _get_token_and_client(token_provider)
        return await _send_invite_reminder(client, token, entity_id, entity_type, email, subject, message, ctx=ctx)

    @mcp.tool(
        name="cancel_invite",
        description="Cancel all active (pending) signing invites on a document or document group.",
        annotations=ToolAnnotations(
            title="Cancel signing invite",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["invite", "cancel", "document", "document_group", "workflow"],
    )
    async def cancel_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description=("Type of entity: 'document' or 'document_group' (optional). Auto-detected if not provided (tries document_group first). Pass explicitly to save one API call.")),
        ] = None,
        reason: Annotated[
            str | None,
            Field(description="Optional reason for cancellation"),
        ] = None,
    ) -> CancelInviteResponse:
        """Cancel all active (pending) signing invites on a document or document group.

        Auto-detects entity type when not provided by trying document_group first,
        then document. Detects invite type (field vs freeform) automatically.

        If all invites are already completed, returns status='completed'.
        If no invite was ever sent, returns status='invite_not_sent'.
        Otherwise cancels pending invites and returns status='cancelled'.

        Args:
            entity_id: ID of the document or document group.
            entity_type: Optional discriminator ('document' or 'document_group').
            reason: Optional cancellation reason forwarded to SignNow API.

        Returns:
            CancelInviteResponse with entity_id, entity_type, status, cancelled_invite_ids.
        """
        token, client = _get_token_and_client(token_provider)
        return _cancel_invite(entity_id, entity_type, reason, token, client)

    @mcp.tool(
        name="update_invite_recipient",
        description=(
            "Replace the signing recipient on a pending field invite for a document or document group. "
            "Finds the pending invite for the current signer and replaces it with a new signer. "
            "For documents: deletes the old invite, creates a replacement, and triggers sending. "
            "For document groups: updates the pending step(s) with the new signer information. "
            "Only field invites are supported — freeform and embedded invites cannot be updated."
        ),
        annotations=ToolAnnotations(
            title="Replace invite recipient",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["invite", "update", "replace", "document", "document_group", "workflow"],
    )
    def update_invite_recipient(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        current_email: Annotated[str, Field(description="Email address of the current signer to replace")],
        new_email: Annotated[str, Field(description="Email address of the new signer")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description=("Type of entity: 'document' or 'document_group' (optional). Auto-detected if not provided (tries document_group first). Pass explicitly to save one API call.")),
        ] = None,
        role: Annotated[
            str | None,
            Field(description="Role name to match (for multi-role documents). If omitted, matches any role."),
        ] = None,
    ) -> UpdateInviteRecipientResponse:
        """Replace the signing recipient on a pending field invite.

        Supports both documents and document groups:

        Documents:
        1. Finds the pending/created field invite matching current_email (and optional role)
        2. Deletes the old invite, creates a replacement for new_email
        3. Triggers sending to the new signer

        Document Groups:
        1. Finds pending steps with actions matching current_email (and optional role)
        2. Updates each step via /invitestep/{step_id}/update endpoint
        3. Returns list of updated step IDs

        Only field invites are supported. Freeform and embedded invites return
        status='unsupported_invite_type'.

        Args:
            entity_id: Document or document group ID.
            current_email: Email of the current signer to replace.
            new_email: Email of the new signer.
            entity_type: Optional entity type discriminator.
            role: Optional role filter for multi-role documents/steps.

        Returns:
            UpdateInviteRecipientResponse with status, new_invite_id, email info, and updated_steps (for document groups).
        """
        token, client = _get_token_and_client(token_provider)
        return _update_invite_recipient(
            entity_id=entity_id,
            entity_type=entity_type,
            current_email=current_email,
            new_email=new_email,
            role=role,
            token=token,
            client=client,
        )

    @mcp.tool(
        name="view_document",
        description=(
            "Generate a read-only embedded view link for a document or document group. "
            "To find an entity by name, first call list_documents or list_templates "
            "to search for it, then pass the returned entity_id here. "
            "In MCP Apps-compatible clients "
            "the document renders inline — no tab switch needed. "
            "In other hosts, the returned view_link is presented as a clickable URL."
        ),
        meta={"ui": {"resourceUri": VIEWER_RESOURCE_URI}},
        annotations=ToolAnnotations(
            title="View document",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["document", "document_group", "view", "preview"],
    )
    def view_document(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group to view")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group'. Skip for auto-detection (tries document_group first)."),
        ] = None,
        link_expiration_minutes: Annotated[
            int | None,
            Field(
                default=None,
                ge=43200,
                le=518400,
                description="Link lifetime in minutes (43200–518400). Defaults to 43200 (30 days) when omitted.",
            ),
        ] = None,
    ) -> ViewDocumentResponse:
        """Generate a read-only embedded view link for a document or document group.

        Calls POST /v2/documents/{id}/embedded-view or POST /v2/document-groups/{id}/embedded-view.
        No SignNow login required to open the link. Auto-detects entity type when omitted.

        Tip: use list_documents first to discover document IDs by name or criteria.
        Tip: if entity_type is known, pass it explicitly to avoid an extra auto-detection GET.

        Args:
            entity_id: Document ID or document group ID.
            entity_type: Optional discriminator ('document' or 'document_group').
            link_expiration_minutes: Optional link lifetime in minutes (43200–518400).

        Returns:
            ViewDocumentResponse with view_link, document_name, entity_id, entity_type.
        """
        token, client = _get_token_and_client(token_provider)
        return _view_document(entity_id, entity_type, link_expiration_minutes, token, client)

    @mcp.resource(
        VIEWER_RESOURCE_URI,
        name="document_viewer_app",
        description="MCP Apps inline viewer for SignNow documents. Returns an HTML page that renders an embedded document view inside a sandboxed iframe.",
        mime_type="text/html;profile=mcp-app",
    )
    def get_document_viewer_ui() -> str:
        """Return the MCP Apps HTML viewer for inline document rendering."""
        return _VIEWER_HTML

    @mcp.resource(
        SENDER_RESOURCE_URI,
        name="embedded_sender_app",
        description="MCP Apps inline UI for SignNow Embedded Sender. Returns an HTML page that renders the embedded sender inside a sandboxed iframe.",
        mime_type="text/html;profile=mcp-app",
    )
    def get_embedded_sender_ui() -> str:
        """Return the MCP Apps HTML for inline embedded sender rendering."""
        return _SENDER_HTML

    async def _list_contacts_impl(query: str | None = None, per_page: int = 15) -> ContactListResponse:
        token, client = _get_token_and_client(token_provider)
        return await _list_contacts(token, client, query=query, per_page=per_page)

    @mcp.tool(
        name="list_contacts",
        description="Search CRM contacts by name, email, or phone. Use this tool before send_invite to resolve a recipient's email address by their name." + TOOL_FALLBACK_SUFFIX,
        annotations=ToolAnnotations(
            title="List CRM contacts",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        tags=["contacts", "crm", "list"],
    )
    async def list_contacts(
        ctx: Context,
        query: Annotated[
            str | None,
            Field(description="Filter contacts by name, email, or phone (partial match). Omit to return the first per_page contacts."),
        ] = None,
        per_page: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of contacts to return (1–100, default 15)"),
        ] = 15,
    ) -> ContactListResponse:
        """Search CRM contacts by name, email, or phone.

        Returns a curated list of contacts with id, email, first_name, last_name, and company.
        When ``query`` is provided, performs a partial (LIKE) match against email, first name,
        last name, full name, and phone simultaneously.
        When no contacts match, an empty list is returned — this is not an error.

        Args:
            query: Partial name, email, or phone string to filter contacts. Omit to return the first per_page contacts.
            per_page: Maximum number of contacts to return (1–100, default 15).
        """
        return await _list_contacts_impl(query=query, per_page=per_page)

    @mcp.resource(
        "signnow://contacts{?query,per_page}",
        name="list_contacts_resource",
        description="Search CRM contacts by name, email, or phone. Use this resource before send_invite to resolve a recipient's email address by their name." + RESOURCE_PREFERRED_SUFFIX,
        tags=["contacts", "crm", "list"],
        mime_type="application/json",
    )
    async def list_contacts_resource(
        ctx: Context,
        query: Annotated[
            str | None,
            Field(description="Filter contacts by name, email, or phone (partial match). Omit to return the first per_page contacts."),
        ] = None,
        per_page: Annotated[
            int,
            Field(ge=1, le=100, description="Maximum number of contacts to return (1–100, default 15)"),
        ] = 15,
    ) -> ContactListResponse:
        return await _list_contacts_impl(query=query, per_page=per_page)

    return
