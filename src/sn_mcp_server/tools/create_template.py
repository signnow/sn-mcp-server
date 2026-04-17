"""
Create template business logic for SignNow MCP server.

Converts a document or document group into a reusable SignNow template.
Supports auto-detection of entity type (document_group tried first, document as fallback).

Auto-detection order follows the AGENTS.md standard:
  1. document_group (modern entity type, v2 API)
  2. document (legacy fallback)
"""

from __future__ import annotations

from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError, SignNowAPIHTTPError
from signnow_client.models.document_groups import CreateDocumentGroupTemplateFromGroupRequest
from signnow_client.models.templates_and_documents import CreateTemplateRequest

from .models import CreateTemplateResult


def _is_not_found_error(exc: SignNowAPIHTTPError) -> bool:
    """Return True when a 400 error represents a 'not found' response from SignNow.

    SignNow returns 400 with error code 65582 on not-found conditions, with varying
    messages depending on the endpoint:
      - /template (create)  → "Document not found"
    """
    if exc.status_code == 400:
        errors = (exc.response_data or {}).get("errors", [])
        return any(e.get("code") == 65582 or "not found" in e.get("message", "").lower() or "unable to find" in e.get("message", "").lower() for e in errors)
    return False


def create_template(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    template_name: str,
    entity_type: Literal["document", "document_group"] | None = None,
) -> CreateTemplateResult:
    """Convert a document or document group into a reusable template.

    When entity_type is omitted, auto-detects by trying document_group first
    (modern path), then document (legacy path). Follows the standard
    auto-detection order mandated by AGENTS.md.

    For document groups, SignNow returns 202 Accepted — template creation is
    asynchronous. template_id will be None; use list_all_templates after a
    short delay to find the created template group.

    Args:
        client: Authenticated SignNow API client.
        token: Bearer access token.
        entity_id: ID of the source document or document group.
        template_name: Desired name for the new template.
        entity_type: Optional. 'document' | 'document_group' | None (auto-detect).

    Returns:
        CreateTemplateResult with template_id (or None for async doc group path),
        template_name, and entity_type.

    Raises:
        ValueError: entity_type is invalid, template_name/entity_id is empty,
                    or entity not found during auto-detection.
        SignNowAPIError: On unexpected API failures.
    """
    if not template_name.strip():
        raise ValueError("template_name must not be empty")

    if not entity_id.strip():
        raise ValueError("entity_id must not be empty")

    if entity_type is not None and entity_type not in {"document", "document_group"}:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'document' or 'document_group'.")

    if entity_type is None:
        # Auto-detection: try document_group first (modern), fall back to document (legacy).
        # Non-404 errors (401, 403, 429, 500…) must not be swallowed.
        try:
            client.get_document_group_v2(token, entity_id)
            entity_type = "document_group"
        except SignNowAPIError as exc:
            if exc.status_code != 404:
                raise
            try:
                client.get_document(token, entity_id)
                entity_type = "document"
            except SignNowAPIError as exc2:
                if exc2.status_code != 404:
                    raise
                raise ValueError(f"Entity {entity_id} not found as document or document_group") from None

    if entity_type == "document_group":
        return _create_from_document_group(client, token, entity_id, template_name)

    return _create_from_document(client, token, entity_id, template_name)


def _create_from_document_group(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    template_name: str,
) -> CreateTemplateResult:
    """Create a document group template from an existing document group.

    SignNow processes this asynchronously (202 Accepted) — no template ID is
    returned. The caller should use list_all_templates after a short delay.
    """
    try:
        client.create_document_group_template_from_group(
            token,
            entity_id,
            CreateDocumentGroupTemplateFromGroupRequest(name=template_name),
        )
    except SignNowAPIHTTPError as exc:
        if exc.status_code == 404:
            raise ValueError(f"Document group not found: {entity_id}") from None
        if exc.status_code == 403:
            raise ValueError(f"No permission to templatize document group: {entity_id}") from None
        raise

    return CreateTemplateResult(
        template_id=None,
        template_name=template_name,
        entity_type="document_group",
    )


def _create_from_document(
    client: SignNowAPIClient,
    token: str,
    entity_id: str,
    template_name: str,
) -> CreateTemplateResult:
    """Create a template from an existing document.

    SignNow returns the new template ID synchronously.
    """
    try:
        response = client.create_template(token, CreateTemplateRequest(document_id=entity_id, document_name=template_name))
    except SignNowAPIHTTPError as exc:
        if exc.status_code == 404 or _is_not_found_error(exc):
            raise ValueError(f"Document not found: {entity_id}") from None
        if exc.status_code == 403:
            raise ValueError(f"No permission to templatize document: {entity_id}") from None
        raise

    return CreateTemplateResult(
        template_id=response.id,
        template_name=template_name,
        entity_type="document",
    )
