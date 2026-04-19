"""
Utility functions for SignNow MCP server tools.

This module contains shared utility functions used across multiple tool modules.
"""

from typing import Literal, Protocol, Union

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIHTTPError
from signnow_client.models.folders_lite import RoleLite, _normalize_roles


class HasName(Protocol):
    """Protocol for objects that have a name attribute."""

    name: str | None


RoleType = Union[RoleLite, str, dict[str, str], HasName]


def _is_not_found_error(exc: SignNowAPIHTTPError) -> bool:
    """Return True when a 400 error represents a 'not found' response from SignNow.

    SignNow returns 400 with error code 65582 on not-found conditions, with varying
    messages depending on the endpoint:
      - /template/{id}/copy          → "Document not found"
      - /documentgroup/template/{id} → "unable to find document group template"
    """
    if exc.status_code == 400:
        errors = (exc.response_data or {}).get("errors", [])
        return any(e.get("code") == 65582 or "not found" in e.get("message", "").lower() or "unable to find" in e.get("message", "").lower() for e in errors)
    return False


def extract_role_names(roles: list[RoleType] | None) -> list[str]:
    """Extract role names from various role representations.

    This function uses _normalize_roles from folders_lite and converts None to empty list
    for compatibility with code that expects list[str] instead of list[str] | None.

    This function handles multiple role formats that can come from the SignNow API:
    - list[str]: Direct list of role names
    - list[dict]: List of dictionaries with "name" key
    - list[RoleLite]: List of Pydantic RoleLite models
    - list[HasName]: List of objects with name attribute

    Args:
        roles: List of roles in any supported format, or None

    Returns:
        List of role names (strings), empty list if roles is None or empty

    Examples:
        >>> extract_role_names(["Signer", "Reviewer"])
        ['Signer', 'Reviewer']
        >>> extract_role_names([{"name": "Signer"}, {"name": "Reviewer"}])
        ['Signer', 'Reviewer']
        >>> extract_role_names(None)
        []
    """
    normalized = _normalize_roles(roles)
    return normalized if normalized is not None else []


def _detect_entity_type(
    entity_id: str,
    token: str,
    client: SignNowAPIClient,
) -> Literal["document_group", "template_group", "document", "template"]:
    """Detect the entity type for the given ID using a 4-probe waterfall.

    Probe order (stops at first match, re-raises non-detection errors):
      1. get_document_group       → "document_group"
      2. get_document_group_template → "template_group"
      3. get_document             → "document"
      4. (no probe)               → "template" (last resort)

    Args:
        entity_id: ID to classify
        token: Access token for SignNow API
        client: SignNow API client instance

    Returns:
        entity_type: Detected entity type as a string literal
    """
    # todo: return entity as well to avoid redundant fetch in some flows
    try:
        client.get_document_group(token, entity_id)
        return "document_group"
    except SignNowAPIHTTPError as exc:
        if exc.status_code != 404 and not _is_not_found_error(exc):
            raise

    try:
        client.get_document_group_template(token, entity_id)
        return "template_group"
    except SignNowAPIHTTPError as exc:
        if exc.status_code != 404 and not _is_not_found_error(exc):
            raise

    document = client.get_document(token, entity_id)

    return "template" if document.template else "document"
