"""SignNow CRM Contacts API models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CrmContactPhone(BaseModel):
    """Phone information embedded in a CRM contact."""

    number: str | None = Field(None, description="Phone number")
    country_code: str | None = Field(None, description="Country code (e.g. US)")


class CrmContactCompany(BaseModel):
    """Company information embedded in a CRM contact."""

    name: str | None = Field(None, description="Company name")


class CrmContact(BaseModel):
    """Single contact from GET /v2/crm/contacts response.

    Captures all fields returned by the API. The tool layer selects
    only the subset needed for agent decisions.
    """

    id: str = Field(..., description="Contact ID")
    email: str = Field(..., description="Contact email address")
    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    phone: CrmContactPhone | None = Field(None, description="Phone info")
    company: CrmContactCompany | None = Field(None, description="Company info")
    description: str | None = Field(None, description="Contact description")


class CrmContactsResponse(BaseModel):
    """Top-level response from GET /v2/crm/contacts.

    Only the ``data`` array is consumed; pagination metadata is intentionally
    ignored at the tool layer for token efficiency. Extra top-level keys
    (``meta``, pagination fields) are silently ignored by Pydantic.
    """

    data: list[CrmContact] = Field(default_factory=list, description="List of contacts")
