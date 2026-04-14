"""CRM contact listing functions for SignNow MCP server."""

from __future__ import annotations

from signnow_client import SignNowAPIClient

from .models import ContactItem, ContactListResponse


async def _list_contacts(
    token: str,
    client: SignNowAPIClient,
    query: str | None = None,
    per_page: int = 15,
) -> ContactListResponse:
    """Retrieve CRM contacts and curate the response for agent consumption.

    Calls GET /v2/crm/contacts. When ``query`` is provided, the API performs a
    LIKE match against email, first_name, last_name, full_name, and phone
    simultaneously using the ``_OR`` filter combinator.

    Returns an empty list when no contacts match — this is not an error.

    Args:
        token: Access token for SignNow API.
        client: SignNow API client instance.
        query: Optional partial string to filter contacts by name, email, or phone.
        per_page: Maximum number of contacts to return (1–100, default 15).

    Returns:
        ContactListResponse with curated list of matching contacts and their count.

    Raises:
        ValueError: If ``per_page`` is outside the 1–100 range.
        SignNowAPIAuthenticationError: If the token is invalid or expired.
        SignNowAPIRateLimitError: If the SignNow API rate limit is exceeded.
        SignNowAPIServerError: If SignNow returns a server-side error.
    """
    if per_page < 1 or per_page > 100:
        raise ValueError(f"per_page must be between 1 and 100, got {per_page}")

    api_response = client.get_contacts(token, query=query, per_page=per_page)

    contacts = [
        ContactItem(
            id=c.id,
            email=c.email,
            first_name=c.first_name,
            last_name=c.last_name,
            company=c.company.name if c.company else None,
        )
        for c in api_response.data
    ]

    return ContactListResponse(contacts=contacts, count=len(contacts))
