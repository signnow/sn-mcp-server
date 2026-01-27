"""
Utility functions for SignNow MCP server tools.

This module contains shared utility functions used across multiple tool modules.
"""

from typing import Protocol, Union

from signnow_client.models.folders_lite import RoleLite, _normalize_roles


class HasName(Protocol):
    """Protocol for objects that have a name attribute."""

    name: str | None


RoleType = Union[RoleLite, str, dict[str, str], HasName]


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
