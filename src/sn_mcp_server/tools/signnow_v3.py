"""
MCP Tool registrations — version 3.0.

Per the versioning governance rule in ``AGENTS.md``, every tool contract change
(input/output parameters) or brand-new tool is introduced here as a v3.0 tool;
v1.0 (``signnow_v1.py``) and v2.0 (``signnow.py``) contracts are frozen. FastMCP
serves the highest registered version by default, so clients transparently get
v3.0 while a client pinning v2.0 keeps the older contract.

v3.0 tools registered here:
  - upload_document  (adds the kind parameter — document|template — to the v2.0 upload_document contract)
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

from fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from sn_mcp_server.token_provider import TokenProvider

from .document import _upload_document
from .models import UploadDocumentResponse
from .signnow import _get_token_and_client, _resolve_upload_resource


def bind(mcp: Any, cfg: Any) -> None:  # noqa: ANN401
    """Register v3.0 tools on the FastMCP instance."""
    token_provider = TokenProvider()

    @mcp.tool(
        name="upload_document",
        version="3.0",
        description=(
            "Upload a file to SignNow from a local file path, public URL, or MCP resource attachment. "
            "By default (kind='document') the file is uploaded as a regular document; set kind='template' to "
            "upload it as a reusable template instead (a blueprint you clone into documents via create_from_template). "
            "Supported file types: PDF, DOC, DOCX, PNG, JPG, JPEG. Max file size: 40 MB. "
            "On success the response includes a 'document_id' (a template ID when kind='template'), a "
            "'next_steps' array, and an 'agent_guidance' string — the next_steps adapt to kind "
            "(document: prepare invite / send for signing / self-sign; template: create a document from it / "
            "edit its fields and roles). Present those options to the user and wait for them to choose before "
            "calling any follow-up tool. "
            "NOTE: For URL uploads without an explicit filename, the returned filename is locally inferred "
            "and may differ from how SignNow names the entity; pass filename to set the name explicitly."
        ),
        annotations=ToolAnnotations(
            title="Upload document",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
        tags=["document", "template", "upload", "file"],
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
                    "Optional custom name for the entity as it will appear in SignNow. "
                    "If omitted, the name is derived from the file path, URL, or resource URI. "
                    "Required when using resource_uri and the filename cannot be inferred."
                ),
            ),
        ] = None,
        kind: Annotated[
            Literal["document", "template"],
            Field(
                description=(
                    "What to create from the uploaded file: 'document' (default) for a regular document, "
                    "or 'template' for a reusable template. With 'template' the returned document_id is a "
                    "template ID, and next_steps switch to the template follow-ups "
                    "(create_from_template / create_embedded_editor)."
                ),
            ),
        ] = "document",
    ) -> UploadDocumentResponse:
        """Upload a document — or, with kind='template', a reusable template — to SignNow.

        Provide exactly one of: resource_uri, file_path, or file_url.
        Supported formats: PDF, DOC, DOCX, PNG, JPG, JPEG. Max file size: 40 MB.

        Preferred source order:
        1. resource_uri — if the user @-attached a file in their MCP client
        2. file_path — if the user provided a local path
        3. file_url — if the user provided a public URL

        After upload, present the returned next_steps to the user and wait for them to choose.
        For a document (kind='document'):
        1. Prepare a role-based invite (create_embedded_sending)
        2. Send for signing as a freeform invite (send_invite with recipient email)
        3. Sign the document yourself (send_invite with self_sign=True)
        For a template (kind='template'):
        1. Create a document from this template (create_from_template)
        2. Edit the template's fields and roles (create_embedded_editor)

        Args:
            ctx: FastMCP context (injected)
            resource_uri: MCP resource URI from an attached file
            file_path: Local file path (absolute or ~-relative)
            file_url: Public URL to the file
            filename: Optional custom entity name in SignNow
            kind: 'document' (default) for a regular document, or 'template' for a reusable template
        """
        token, client = _get_token_and_client(token_provider)

        # Validate mutually-exclusive source inputs before any I/O
        provided = sum(x is not None for x in (resource_uri, file_path, file_url))
        if provided > 1:
            raise ValueError("Provide exactly one of resource_uri, file_path, or file_url — not multiple")
        if provided == 0:
            raise ValueError("Provide one of: resource_uri, file_path, or file_url")

        resource_bytes, filename = await _resolve_upload_resource(ctx, resource_uri, filename)

        # Run synchronous _upload_document off the async event loop
        return await asyncio.to_thread(
            _upload_document,
            client=client,
            token=token,
            resource_bytes=resource_bytes,
            file_path=file_path,
            file_url=file_url,
            filename=filename,
            make_template=kind == "template",
        )
