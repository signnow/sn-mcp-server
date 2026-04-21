"""
Document Tools

Tools for working with documents in SignNow.
"""

import pathlib
import time
from typing import Literal
from urllib.parse import urlparse

from signnow_client import SignNowAPIClient
from signnow_client.models.document_groups import (
    GetDocumentGroupTemplateResponse,
    GetDocumentGroupV2Response,
)
from signnow_client.models.templates_and_documents import (
    CreateDocumentFromUrlRequest,
    DocumentResponse,
)

from .models import (
    DocumentField,
    DocumentGroup,
    DocumentGroupDocument,
    SimplifiedInvite,
    UpdateDocumentFields,
    UpdateDocumentFieldsResponse,
    UpdateDocumentFieldsResult,
    UploadDocumentResponse,
)

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg"})
MAX_FILE_SIZE_BYTES: int = 40 * 1024 * 1024  # SignNow API limit
SAFE_UPLOAD_BASE: pathlib.Path = pathlib.Path.home().resolve()


def _validate_extension(filename: str) -> None:
    """Validate filename has a supported extension.

    Raises ValueError with a clear message for missing or unsupported extensions.
    """
    ext = pathlib.Path(filename).suffix.lower()
    if not ext:
        raise ValueError(f"Cannot determine file type for '{filename}' — filename has no extension. Add an extension. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")


def _upload_document(
    *,
    client: SignNowAPIClient,
    token: str,
    file_path: str | None = None,
    file_url: str | None = None,
    resource_bytes: bytes | None = None,
    filename: str | None = None,
) -> UploadDocumentResponse:
    """Upload a document to SignNow from a local path, public URL, or pre-read MCP resource bytes.

    Exactly one of ``file_path``, ``file_url``, or ``resource_bytes`` must be provided.
    If ``filename`` is omitted, it is derived from the path or URL (required when resource_bytes used).

    Local-path upload (source='local_file'):
      - Expands ``~`` and resolves to absolute path.
      - Validates file extension against ALLOWED_EXTENSIONS.
      - Reads bytes and checks against MAX_FILE_SIZE_BYTES.
      - Calls ``client.upload_document()`` → ``POST /document``.

    URL upload (source='url'):
      - Validates URL scheme is ``https`` (or ``http`` for local dev).
      - Delegates to ``client.create_document_from_url()`` → ``POST /v2/documents/url``.
      - SignNow server fetches the file — no local download.

    Resource bytes upload (source='resource'):
      - Bytes already resolved by the caller via ``ctx.read_resource()``.
      - Validates file extension against ALLOWED_EXTENSIONS (from filename).
      - Checks size against MAX_FILE_SIZE_BYTES.
      - Calls ``client.upload_document()`` → ``POST /document``.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        file_path: Absolute or ~ path to a local file
        file_url: Publicly accessible URL to the file
        resource_bytes: Raw file bytes read from an MCP resource (caller resolves resource_uri)
        filename: Custom name for the document in SignNow.
                  Required when resource_bytes provided; otherwise derived from path/URL.

    Returns:
        UploadDocumentResponse with document_id, filename, and source

    Raises:
        ValueError: Multiple or no sources provided, unsupported extension, file too large,
                    file not found, filename missing for resource bytes
    """
    provided = sum(x is not None for x in (file_path, file_url, resource_bytes))
    if provided > 1:
        raise ValueError("Provide exactly one of resource_uri, file_path, or file_url — not multiple")
    if provided == 0:
        raise ValueError("Provide one of: resource_uri, file_path, or file_url")

    if resource_bytes is not None:
        if filename is None:
            raise ValueError("filename is required when uploading from a resource URI")
        _validate_extension(filename)
        if len(resource_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File too large ({len(resource_bytes)} bytes). Maximum allowed: {MAX_FILE_SIZE_BYTES} bytes (40 MB)")
        response = client.upload_document(token=token, file_content=resource_bytes, filename=filename, check_fields=True)
        return UploadDocumentResponse(document_id=response.id, filename=filename, source="resource")

    if file_path is not None:
        path = pathlib.Path(file_path).expanduser().resolve()
        # C-1/C-2: Directory containment — prevent path traversal and symlink attacks
        try:
            path.relative_to(SAFE_UPLOAD_BASE)
        except ValueError:
            raise ValueError(f"file_path must be within the home directory ({SAFE_UPLOAD_BASE}). Resolved path '{path}' is outside the allowed root.") from None
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        _validate_extension(path.name if not filename else filename)
        # H-4: Read first, then check size to eliminate TOCTOU race
        file_content = path.read_bytes()
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File too large ({len(file_content):,} bytes). Maximum allowed: {MAX_FILE_SIZE_BYTES:,} bytes (40 MB)")
        effective_filename = filename if filename else path.name
        response = client.upload_document(token=token, file_content=file_content, filename=effective_filename, check_fields=True)
        return UploadDocumentResponse(document_id=response.id, filename=effective_filename, source="local_file")

    # file_url branch — provided == 1 guarantees file_url is not None at this point
    assert file_url is not None  # noqa: S101  # unreachable: provided==1 guarantees this
    parsed = urlparse(file_url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"URL must use http or https (got '{parsed.scheme}')")
    if not parsed.netloc:
        raise ValueError(f"URL must include a hostname: {file_url!r}")
    url_filename = pathlib.PurePosixPath(parsed.path).name
    url_effective_filename: str | None = filename if filename else (url_filename if url_filename else None)
    if url_effective_filename:
        ext = pathlib.Path(url_effective_filename).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    request = CreateDocumentFromUrlRequest(url=file_url, check_fields=True)
    url_response = client.create_document_from_url(token=token, request_data=request)
    # NOTE (H-2): CreateDocumentFromUrlRequest has no 'name' field — url_effective_filename
    # is locally inferred and not transmitted to SignNow. The actual document name in
    # SignNow may differ (set by SignNow from URL path or Content-Disposition header).
    return UploadDocumentResponse(document_id=url_response.id, filename=url_effective_filename, source="url")


def _get_full_document(client: SignNowAPIClient, token: str, document_id: str, document_data: DocumentResponse) -> DocumentGroupDocument:
    """
    Get full document information including field values.

    This function retrieves a document with all its metadata and field values.
    The basic information (id, name, roles) comes from the document endpoint,
    while field values are retrieved separately using get_document_fields.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_id: ID of the document to retrieve
        document_data: Pre-fetched document data to avoid duplicate API calls

    Returns:
        DocumentGroupDocument with complete document information including field values
    """

    # Use provided document data
    document_response = document_data

    # Create DocumentField objects with values
    document_fields = []

    for field in document_response.fields:
        if field.type == "text":
            document_fields.append(
                DocumentField(
                    id=field.id,
                    type=field.type,
                    role_id=field.role,  # Using role name as role_id for consistency
                    value=field.json_attributes.prefilled_text or "",
                    name=field.json_attributes.name,
                )
            )

    return DocumentGroupDocument(id=document_response.id, name=document_response.document_name, roles=[role.name for role in document_response.roles], fields=document_fields)


def _get_full_document_group(client: SignNowAPIClient, token: str, group_data: GetDocumentGroupV2Response) -> DocumentGroup:
    """
    Get full document group information including all documents with their field values.

    This function retrieves a document group using v2 API and for each document in the group,
    gets the complete document information including field values.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_group_id: ID of the document group to retrieve
        group_data: Pre-fetched group data to avoid duplicate API calls

    Returns:
        DocumentGroup with complete information including all documents with field values
    """

    data = group_data.data

    full_documents = []
    all_field_invites = []
    for doc in data.documents:
        if doc.field_invites:
            all_field_invites.extend(doc.field_invites)
        document_data = client.get_document(token, doc.id)
        full_doc = _get_full_document(client=client, token=token, document_id=doc.id, document_data=document_data)
        full_documents.append(full_doc)

    now = int(time.time())
    invite = SimplifiedInvite.from_document_group_v2(
        invite_id=data.invite_id,
        raw_status=data.state,
        field_invites=all_field_invites if all_field_invites else None,
        now=now,
    )

    return DocumentGroup(
        last_updated=data.created,
        entity_id=data.id,
        group_name=data.name,
        entity_type="document_group",
        invite=invite,
        documents=full_documents,
    )


def _get_full_template_group(client: SignNowAPIClient, token: str, template_group_data: GetDocumentGroupTemplateResponse) -> DocumentGroup:
    """
    Get full template group information including all templates with their field values.

    This function retrieves a template group and for each template in the group,
    gets the complete template information including field values.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        template_group_data: Pre-fetched template group data to avoid duplicate API calls

    Returns:
        DocumentGroup with complete information including all templates with field values
    """

    # Get full document information for each template in the group
    full_documents = []
    for template in template_group_data.templates:
        # Get template data as document (templates are documents in SignNow)
        document_data = client.get_document(token, template.id)
        full_doc = _get_full_document(client=client, token=token, document_id=template.id, document_data=document_data)
        full_documents.append(full_doc)

    # Create DocumentGroup with full template information
    return DocumentGroup(
        last_updated=0,  # Not available in template group response
        entity_id=template_group_data.id,
        group_name=template_group_data.group_name,
        entity_type="template_group",
        invite=None,  # Not applicable for template groups
        documents=full_documents,
    )


def _get_document(client: SignNowAPIClient, token: str, entity_id: str, entity_type: Literal["document", "document_group", "template", "template_group"] | None = None) -> DocumentGroup:
    """
    Get document or document group information with full field values.

    This function determines the entity type if not provided and returns
    a DocumentGroup with complete information including field values.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document', 'template', 'template_group' or 'document_group' (optional)

    Returns:
        DocumentGroup with complete information including field values

    Raises:
        ValueError: If entity not found as either document or document group
    """

    # Auto-detect entity type when not provided by probing document → document_group → template_group.
    # Each fallback swallows the prior probe's error because "not found as this type" is the
    # expected negative signal that drives the cascade; the final arm raises if all probes fail.
    if not entity_type:
        try:
            document_data = client.get_document(token, entity_id)
            return _get_single_document_as_group(client, token, entity_id, document_data)
        except Exception:  # noqa: S110
            pass
        try:
            group_data = client.get_document_group_v2(token, entity_id)
            return _get_full_document_group(client, token, group_data)
        except Exception:  # noqa: S110
            pass
        try:
            template_group_data = client.get_document_group_template(token, entity_id)
            return _get_full_template_group(client, token, template_group_data)
        except Exception:
            raise ValueError(f"Entity with ID {entity_id} not found as either document, template, template group or document group") from None

    # Entity type is provided — dispatch directly to the appropriate fetcher.
    if entity_type == "document_group":
        return _get_full_document_group(client, token, client.get_document_group_v2(token, entity_id))
    if entity_type == "template_group":
        return _get_full_template_group(client, token, client.get_document_group_template(token, entity_id))
    # entity_type == "document" or "template"
    return _get_single_document_as_group(client, token, entity_id, client.get_document(token, entity_id))


def _get_single_document_as_group(client: SignNowAPIClient, token: str, document_id: str, document_data: DocumentResponse) -> DocumentGroup:
    """
    Get a single document and return it as a DocumentGroup with one document.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_id: ID of the document to retrieve
        document_data: Pre-fetched document data to avoid duplicate API calls

    Returns:
        DocumentGroup containing the single document with full field values
    """

    # Get full document information
    full_document = _get_full_document(client, token, document_id, document_data)

    # Create invite from field_invites
    now = int(time.time())
    invite = SimplifiedInvite.from_document_field_invites(document_data.field_invites, now)

    # Create DocumentGroup with single document
    return DocumentGroup(
        last_updated=0,  # Not available for single documents
        entity_id=document_id,
        group_name=full_document.name,
        entity_type="document",
        invite=invite,
        documents=[full_document],
    )


def _update_document_fields(client: SignNowAPIClient, token: str, update_requests: list[UpdateDocumentFields]) -> UpdateDocumentFieldsResponse:
    """
    Update fields for multiple documents.

    This function updates text fields in multiple documents using the SignNow API.
    Only text fields can be updated using the prefill_text_fields endpoint.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        update_requests: List of UpdateDocumentFields with document IDs and fields to update

    Returns:
        UpdateDocumentFieldsResponse with results for each document update
    """

    results = []

    for update_request in update_requests:
        try:
            # Convert FieldToUpdate to PrefillTextField format
            prefill_fields = []
            for field in update_request.fields:
                prefill_fields.append({"field_name": field.name, "prefilled_text": field.value})

            # Create PrefillTextFieldsRequest
            from signnow_client.models.templates_and_documents import (
                PrefillTextField,
                PrefillTextFieldsRequest,
            )

            prefill_request = PrefillTextFieldsRequest(fields=[PrefillTextField(field_name=field.name, prefilled_text=field.value) for field in update_request.fields])

            # Update fields using the client
            success = client.prefill_text_fields(token=token, document_id=update_request.document_id, request_data=prefill_request)

            results.append(UpdateDocumentFieldsResult(document_id=update_request.document_id, updated=success, reason=None))  # No reason needed for success

        except Exception as e:
            # Log error and mark as failed
            error_message = str(e)
            results.append(UpdateDocumentFieldsResult(document_id=update_request.document_id, updated=False, reason=error_message))

    return UpdateDocumentFieldsResponse(results=results)
