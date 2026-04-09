"""Unit tests for list_contacts module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIAuthenticationError
from signnow_client.models.contacts import CrmContact, CrmContactCompany, CrmContactsResponse
from sn_mcp_server.tools.list_contacts import _list_contacts
from sn_mcp_server.tools.models import ContactItem, ContactListResponse


class TestListContacts:
    """Test cases for _list_contacts."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    @pytest.fixture
    def contact_with_company(self) -> CrmContact:
        """Create a CrmContact with all fields populated."""
        return CrmContact(
            id="contact-123",
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            company=CrmContactCompany(name="Acme Corp"),
        )

    @pytest.fixture
    def contact_minimal(self) -> CrmContact:
        """Create a CrmContact with only required fields."""
        return CrmContact(
            id="contact-456",
            email="minimal@example.com",
        )

    async def test_returns_curated_contact_list(self, mock_client: MagicMock, contact_with_company: CrmContact) -> None:
        """Test that contacts are curated into ContactListResponse."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[contact_with_company])

        result = await _list_contacts("tok", mock_client)

        assert isinstance(result, ContactListResponse)
        assert result.count == 1
        assert len(result.contacts) == 1

    async def test_contact_fields_are_curated(self, mock_client: MagicMock, contact_with_company: CrmContact) -> None:
        """Test each curated field is correctly mapped from API model."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[contact_with_company])

        result = await _list_contacts("tok", mock_client)

        item = result.contacts[0]
        assert isinstance(item, ContactItem)
        assert item.id == "contact-123"
        assert item.email == "john.doe@example.com"
        assert item.first_name == "John"
        assert item.last_name == "Doe"
        assert item.company == "Acme Corp"

    async def test_company_is_none_when_absent(self, mock_client: MagicMock, contact_minimal: CrmContact) -> None:
        """Test that company is None when contact has no company."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[contact_minimal])

        result = await _list_contacts("tok", mock_client)

        assert result.contacts[0].company is None

    async def test_optional_name_fields_are_none(self, mock_client: MagicMock, contact_minimal: CrmContact) -> None:
        """Test that first_name and last_name are None when absent on contact."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[contact_minimal])

        result = await _list_contacts("tok", mock_client)

        item = result.contacts[0]
        assert item.first_name is None
        assert item.last_name is None

    async def test_empty_data_returns_empty_list(self, mock_client: MagicMock) -> None:
        """Test that empty API data returns ContactListResponse with zero count."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[])

        result = await _list_contacts("tok", mock_client)

        assert result.count == 0
        assert result.contacts == []

    async def test_count_matches_contacts_length(
        self,
        mock_client: MagicMock,
        contact_with_company: CrmContact,
        contact_minimal: CrmContact,
    ) -> None:
        """Test that count always equals the number of contact items."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[contact_with_company, contact_minimal])

        result = await _list_contacts("tok", mock_client)

        assert result.count == 2
        assert len(result.contacts) == result.count

    async def test_passes_query_to_client(self, mock_client: MagicMock) -> None:
        """Test that query parameter is forwarded to client.get_contacts."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[])

        await _list_contacts("tok", mock_client, query="john")

        mock_client.get_contacts.assert_called_once_with("tok", query="john", per_page=15)

    async def test_passes_per_page_to_client(self, mock_client: MagicMock) -> None:
        """Test that per_page parameter is forwarded to client.get_contacts."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[])

        await _list_contacts("tok", mock_client, per_page=50)

        mock_client.get_contacts.assert_called_once_with("tok", query=None, per_page=50)

    async def test_default_parameters_passed_to_client(self, mock_client: MagicMock) -> None:
        """Test that default query=None and per_page=15 are forwarded."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[])

        await _list_contacts("tok", mock_client)

        mock_client.get_contacts.assert_called_once_with("tok", query=None, per_page=15)

    async def test_per_page_zero_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that per_page=0 raises ValueError before calling the API."""
        with pytest.raises(ValueError, match="per_page must be between 1 and 100"):
            await _list_contacts("tok", mock_client, per_page=0)

        mock_client.get_contacts.assert_not_called()

    async def test_per_page_101_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that per_page=101 raises ValueError before calling the API."""
        with pytest.raises(ValueError, match="per_page must be between 1 and 100"):
            await _list_contacts("tok", mock_client, per_page=101)

        mock_client.get_contacts.assert_not_called()

    async def test_per_page_negative_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that negative per_page raises ValueError."""
        with pytest.raises(ValueError, match="per_page must be between 1 and 100"):
            await _list_contacts("tok", mock_client, per_page=-5)

        mock_client.get_contacts.assert_not_called()

    @pytest.mark.parametrize("per_page", [1, 15, 50, 100])
    async def test_per_page_boundary_values_are_accepted(self, mock_client: MagicMock, per_page: int) -> None:
        """Test that boundary per_page values 1 and 100 are accepted."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[])

        result = await _list_contacts("tok", mock_client, per_page=per_page)

        assert result.count == 0
        mock_client.get_contacts.assert_called_once()

    async def test_auth_error_propagates(self, mock_client: MagicMock) -> None:
        """Test that SignNowAPIAuthenticationError propagates from client."""
        mock_client.get_contacts.side_effect = SignNowAPIAuthenticationError("invalid token")

        with pytest.raises(SignNowAPIAuthenticationError):
            await _list_contacts("bad-tok", mock_client)

    async def test_token_is_passed_to_client(self, mock_client: MagicMock) -> None:
        """Test that the access token is forwarded correctly to client."""
        mock_client.get_contacts.return_value = CrmContactsResponse(data=[])

        await _list_contacts("my-secret-token", mock_client)

        call_args = mock_client.get_contacts.call_args
        assert call_args[0][0] == "my-secret-token"
