from typing import Annotated, Any, Literal

from fastmcp import Context
from fastmcp.server.dependencies import get_http_headers
from mcp.types import ToolAnnotations
from pydantic import Field

from signnow_client import SignNowAPIClient

from ..token_provider import TokenProvider
from .create_from_template import _create_from_template
from .document import _get_document, _update_document_fields
from .document_download_link import _get_document_download_link
from .embedded_editor import (
    _create_embedded_editor,
    _create_embedded_editor_from_template,
)
from .embedded_invite import (
    _create_embedded_invite,
    _create_embedded_invite_from_template,
)
from .embedded_sending import (
    _create_embedded_sending,
    _create_embedded_sending_from_template,
)
from .invite_status import _get_invite_status
from .list_documents import _list_document_groups
from .list_templates import _list_all_templates
from .models import (
    CreateEmbeddedEditorFromTemplateResponse,
    CreateEmbeddedEditorResponse,
    CreateEmbeddedInviteFromTemplateResponse,
    CreateEmbeddedInviteResponse,
    CreateEmbeddedSendingFromTemplateResponse,
    CreateEmbeddedSendingResponse,
    CreateFromTemplateResponse,
    DocumentDownloadLinkResponse,
    DocumentGroup,
    EmbeddedInviteOrder,
    InviteOrder,
    InviteStatus,
    SendInviteFromTemplateResponse,
    SendInviteResponse,
    SendReminderResponse,
    SigningLinkResponse,
    SimplifiedDocumentGroupsResponse,
    TemplateSummaryList,
    UpdateDocumentFields,
    UpdateDocumentFieldsResponse,
)
from .reminder import _send_invite_reminder
from .send_invite import _send_invite, _send_invite_from_template
from .signing_link import _get_signing_link

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
    headers = get_http_headers()
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
            "Send invite to sign a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have template or template_group, use the alternative tool: send_invite_from_template"
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
    def send_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        orders: Annotated[
            list[InviteOrder],
            Field(
                description="List of orders with recipients.",
                examples=[
                    [{"order": 1, "recipients": [{"email": "user@example.com", "role": "Signer 1", "action": "sign"}]}],
                ],
            ),
        ],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> SendInviteResponse:
        """Send invite to sign a document or document group.

        This tool is ONLY for documents and document groups.
        If you have template or template_group, use the alternative tool: send_invite_from_template

        Args:
            entity_id: ID of the document or document group
            orders: List of orders with recipients.
            entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.

        Returns:
            SendInviteResponse with invite ID and entity type
        """
        token, client = _get_token_and_client(token_provider)

        if not orders:
            raise ValueError("orders must contain at least one recipient order")

        return _send_invite(entity_id, entity_type, orders, token, client)

    @mcp.tool(
        name="create_embedded_invite",
        description=(
            "Create embedded invite for signing a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have template or template_group, use the alternative tool: create_embedded_invite_from_template"
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
    def create_embedded_invite(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
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
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
    ) -> CreateEmbeddedInviteResponse:
        """Create embedded invite for signing a document or document group.

        This tool is ONLY for documents and document groups.
        If you have template or template_group, use the alternative tool: create_embedded_invite_from_template

        Args:
            entity_id: ID of the document or document group
            orders: List of orders with recipients.
            entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.

        Returns:
            CreateEmbeddedInviteResponse with invite ID and entity type
        """
        token, client = _get_token_and_client(token_provider)

        return _create_embedded_invite(entity_id, entity_type, orders, token, client)

    @mcp.tool(
        name="create_embedded_sending",
        description=(
            "Create embedded sending for managing, editing, or sending invites for a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have template or template_group, use the alternative tool: create_embedded_sending_from_template"
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
    def create_embedded_sending(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration_minutes: Annotated[int | None, Field(ge=15, le=45, description="Link lifetime in minutes (15–45). Default: 15 min.")] = None,
        type: Annotated[Literal["manage", "edit", "send-invite"] | None, Field(description="Type of sending step: 'manage', 'edit', or 'send-invite'")] = "manage",
    ) -> CreateEmbeddedSendingResponse:
        """Create embedded sending for managing, editing, or sending invites for a document or document group.

        This tool is ONLY for documents and document groups.
        If you have template or template_group, use the alternative tool: create_embedded_sending_from_template

        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            redirect_uri: Optional redirect URI for the sending link
            redirect_target: Optional redirect target for the sending link
            link_expiration_minutes: Link lifetime in minutes (15–45). Default: 15 min.
            type: Specifies the sending step: 'manage' (default), 'edit', 'send-invite'

        Returns:
            CreateEmbeddedSendingResponse with entity type, and URL
        """
        token, client = _get_token_and_client(token_provider)

        return _create_embedded_sending(entity_id, entity_type, redirect_uri, redirect_target, link_expiration_minutes, type, token, client)

    @mcp.tool(
        name="create_embedded_editor",
        description=(
            "Create embedded editor for editing a document or document group. "
            "This tool is ONLY for documents and document groups. "
            "If you have template or template_group, use the alternative tool: create_embedded_editor_from_template"
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
    def create_embedded_editor(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the document or document group")],
        entity_type: Annotated[
            Literal["document", "document_group"] | None,
            Field(description="Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration_minutes: Annotated[int | None, Field(ge=15, le=43200, description="Link lifetime in minutes (15–43200). Default: 15 min.")] = None,
    ) -> CreateEmbeddedEditorResponse:
        """Create embedded editor for editing a document or document group.

        This tool is ONLY for documents and document groups.
        If you have template or template_group, use the alternative tool: create_embedded_editor_from_template

        Args:
            entity_id: ID of the document or document group
            entity_type: Type of entity: 'document' or 'document_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            redirect_uri: Optional redirect URI for the editor link
            redirect_target: Optional redirect target for the editor link
            link_expiration_minutes: Link lifetime in minutes (15–43200). Default: 15 min.

        Returns:
            CreateEmbeddedEditorResponse with editor ID and entity type
        """
        token, client = _get_token_and_client(token_provider)

        return _create_embedded_editor(entity_id, entity_type, redirect_uri, redirect_target, link_expiration_minutes, token, client)

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

    @mcp.tool(
        name="send_invite_from_template",
        description=(
            "Create document/group from template and send invite immediately. "
            "This tool is ONLY for templates and template groups. "
            "If you have document or document_group, use the alternative tool: send_invite"
        ),
        annotations=ToolAnnotations(
            title="Create from template and send invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "document", "document_group", "send_invite", "workflow"],
    )
    async def send_invite_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        orders: Annotated[
            list[InviteOrder],
            Field(
                description="List of orders with recipients for the invite.",
                examples=[
                    [{"order": 1, "recipients": [{"email": "user@example.com", "role": "Signer 1", "action": "sign"}]}],
                ],
            ),
        ],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
    ) -> SendInviteFromTemplateResponse:
        """Create document or document group from template and send invite immediately.

        This tool is ONLY for templates and template groups.
        If you have document or document_group, use the alternative tool: send_invite

        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Sends an invite to the created entity using send_invite

        Args:
            entity_id: ID of the template or template group
            orders: List of orders with recipients for the invite.
            entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            name: Optional name for the new document or document group

        Returns:
            SendInviteFromTemplateResponse with created entity info and invite details
        """
        token, client = _get_token_and_client(token_provider)

        if not orders:
            raise ValueError("orders must contain at least one recipient order")

        return await _send_invite_from_template(entity_id, entity_type, name, orders, token, client, ctx)

    @mcp.tool(
        name="create_embedded_sending_from_template",
        description=(
            "Create document/group from template and create embedded sending immediately. "
            "This tool is ONLY for templates and template groups. "
            "If you have document or document_group, use the alternative tool: create_embedded_sending"
        ),
        annotations=ToolAnnotations(
            title="Create from template and embed sending",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "document", "document_group", "send_invite", "embedded", "workflow"],
    )
    async def create_embedded_sending_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration_minutes: Annotated[int | None, Field(ge=15, le=45, description="Link lifetime in minutes (15–45). Default: 15 min.")] = None,
        type: Annotated[Literal["manage", "edit", "send-invite"] | None, Field(description="Type of sending step: 'manage', 'edit', or 'send-invite'")] = None,
    ) -> CreateEmbeddedSendingFromTemplateResponse:
        """Create document or document group from template and create embedded sending immediately.

        This tool is ONLY for templates and template groups.
        If you have document or document_group, use the alternative tool: create_embedded_sending

        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Creates an embedded sending for the created entity using create_embedded_sending

        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            name: Optional name for the new document or document group
            redirect_uri: Optional redirect URI after completion
            redirect_target: Optional redirect target: 'self', 'blank', or 'self' (default)
            link_expiration_minutes: Link lifetime in minutes (15–45). Default: 15 min.
            type: Type of sending step: 'manage', 'edit', or 'send-invite'

        Returns:
            CreateEmbeddedSendingFromTemplateResponse with created entity info and embedded sending details
        """
        token, client = _get_token_and_client(token_provider)

        return await _create_embedded_sending_from_template(entity_id, entity_type, name, redirect_uri, redirect_target, link_expiration_minutes, type, token, client, ctx)

    @mcp.tool(
        name="create_embedded_editor_from_template",
        description=(
            "Create document/group from template and create embedded editor immediately. "
            "This tool is ONLY for templates and template groups. "
            "If you have document or document_group, use the alternative tool: create_embedded_editor"
        ),
        annotations=ToolAnnotations(
            title="Create from template and embed editor",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "document", "document_group", "embedded_editor", "embedded", "workflow"],
    )
    async def create_embedded_editor_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        name: Annotated[str | None, Field(description="Name for the new document or document group")] = None,
        redirect_uri: Annotated[str | None, Field(description="Optional redirect URI after completion")] = None,
        redirect_target: Annotated[str | None, Field(description="Optional redirect target: 'self' (default), 'blank'")] = None,
        link_expiration_minutes: Annotated[int | None, Field(ge=15, le=43200, description="Link lifetime in minutes (15–43200). Default: 15 min.")] = None,
    ) -> CreateEmbeddedEditorFromTemplateResponse:
        """Create document or document group from template and create embedded editor immediately.

        This tool is ONLY for templates and template groups.
        If you have document or document_group, use the alternative tool: create_embedded_editor

        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Creates an embedded editor for the created entity using create_embedded_editor

        Args:
            entity_id: ID of the template or template group
            entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            name: Optional name for the new document or document group
            redirect_uri: Optional redirect URI after completion
            redirect_target: Optional redirect target: 'self', 'blank', or 'self' (default)
            link_expiration_minutes: Link lifetime in minutes (15–43200). Default: 15 min.

        Returns:
            CreateEmbeddedEditorFromTemplateResponse with created entity info and embedded editor details
        """
        token, client = _get_token_and_client(token_provider)

        # Initialize client and use the imported function from embedded_editor module
        return await _create_embedded_editor_from_template(entity_id, entity_type, name, redirect_uri, redirect_target, link_expiration_minutes, token, client, ctx)

    @mcp.tool(
        name="create_embedded_invite_from_template",
        description=(
            "Create document/group from template and create embedded invite immediately. "
            "This tool is ONLY for templates and template groups. "
            "If you have document or document_group, use the alternative tool: create_embedded_invite"
        ),
        annotations=ToolAnnotations(
            title="Create from template and embed invite",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["template", "template_group", "document", "document_group", "send_invite", "embedded", "workflow"],
    )
    async def create_embedded_invite_from_template(
        ctx: Context,
        entity_id: Annotated[str, Field(description="ID of the template or template group")],
        orders: Annotated[
            list[EmbeddedInviteOrder],
            Field(
                description="List of orders with recipients for the embedded invite.",
                examples=[
                    [{"order": 1, "recipients": [{"email": "user@example.com", "role": "Signer 1", "action": "sign", "auth_method": "none"}]}],
                ],
            ),
        ],
        entity_type: Annotated[
            Literal["template", "template_group"] | None,
            Field(description="Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type."),
        ] = None,
        name: Annotated[str | None, Field(description="Optional name for the new document or document group")] = None,
    ) -> CreateEmbeddedInviteFromTemplateResponse:
        """Create document or document group from template and create embedded invite immediately.

        This tool is ONLY for templates and template groups.
        If you have document or document_group, use the alternative tool: create_embedded_invite

        This tool combines two operations:
        1. Creates a document/group from template using create_from_template
        2. Creates an embedded invite for the created entity using create_embedded_invite

        Args:
            entity_id: ID of the template or template group
            orders: List of orders with recipients for the embedded invite.
            entity_type: Type of entity: 'template' or 'template_group' (optional). If you're passing it, make sure you know what type you have. If it's not found, try using a different type.
            name: Optional name for the new document or document group

        Returns:
            CreateEmbeddedInviteFromTemplateResponse with created entity info and embedded invite details
        """
        token, client = _get_token_and_client(token_provider)

        if not orders:
            raise ValueError("orders must contain at least one recipient order")

        return await _create_embedded_invite_from_template(entity_id, entity_type, name, orders, token, client, ctx)

    def _get_invite_status_impl(ctx: Context, entity_id: str, entity_type: Literal["document", "document_group"] | None) -> InviteStatus:
        token, client = _get_token_and_client(token_provider)
        return _get_invite_status(entity_id, entity_type, token, client)

    @mcp.tool(
        name="get_invite_status",
        description="Get invite status for a document or document group" + TOOL_FALLBACK_SUFFIX,
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
        description="Get invite status for a document or document group" + RESOURCE_PREFERRED_SUFFIX,
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

    # @mcp.tool(
    #     name="upload_document",
    #     description="Upload a document to SignNow",
    #     tags=["document", "upload", "file"]
    # )
    # def upload_document(
    #     ctx: Context,
    #     file_content: Annotated[bytes, Field(description="Document file content as bytes")],
    #     filename: Annotated[str, Field(description="Name of the file to upload")],
    #     check_fields: Annotated[bool, Field(description="Whether to check for fields in the document (default: True)")] = True
    # ) -> UploadDocumentResponse:
    #     """Upload a document to SignNow.

    #     This tool uploads a document file to SignNow and returns the document ID.
    #     The uploaded document can then be used for signing workflows.

    #     Args:
    #         file_content: Document file content as bytes
    #         filename: Name of the file to upload
    #         check_fields: Whether to check for fields in the document (default: True)

    #     Returns:
    #         UploadDocumentResponse with uploaded document ID, filename, and check_fields status
    #     """
    #     headers = get_http_headers()
    #     token = token_provider.get_access_token(headers)

    #     if not token:
    #         raise ValueError("No access token available")

    #     # Initialize client and use the imported function from upload_document module
    #     client = SignNowAPIClient(token_provider.signnow_config)
    #     return _upload_document(file_content, filename, check_fields, token, client)

    @mcp.tool(
        name="send_invite_reminder",
        description=(
            "Send a signing reminder to pending signers on a document or document group. "
            "Auto-detects entity type by trying document_group first, then document as fallback. "
            "Sends a copy of the document via email to each pending signer. "
            "For document groups, only the first document with pending invites is processed."
        ),
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
        Sends a copy of the document to each pending signer via POST /document/{id}/email2.
        For document groups, targets only the first document that has pending invites.
        Pending signers on subsequent documents in the group are not included in any output list.

        Skips signers whose invite is already completed or cancelled (reported in 'skipped').
        API failures per-batch are reported in 'failed' and can be retried.

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

    return
