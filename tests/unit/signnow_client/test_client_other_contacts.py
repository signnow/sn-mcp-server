"""Unit tests for OtherClientMixin.get_contacts method."""

from __future__ import annotations

import json

import pytest

from signnow_client.client_other import OtherClientMixin
from signnow_client.models.contacts import CrmContactsResponse


class _DummyOtherClient(OtherClientMixin):
    """Minimal dummy subclass that captures _get calls without HTTP."""

    def __init__(self) -> None:
        """Initialise captured state."""
        self.last_get: dict | None = None
        self._get_return: CrmContactsResponse = CrmContactsResponse(data=[])

    def _get(self, url: str, headers: dict | None = None, params: dict | None = None, validate_model: object = None) -> CrmContactsResponse:
        """Capture all _get arguments and return preset response."""
        self.last_get = {"url": url, "headers": headers, "params": params}
        return self._get_return


class TestGetContactsUrl:
    """Test that get_contacts sends requests to the correct endpoint."""

    def test_calls_v2_crm_contacts_endpoint(self) -> None:
        """Test that the correct API URL is used."""
        client = _DummyOtherClient()
        client.get_contacts("tok")
        assert client.last_get["url"] == "/v2/crm/contacts"


class TestGetContactsHeaders:
    """Test that get_contacts sends correct request headers."""

    def test_authorization_header_contains_token(self) -> None:
        """Test Bearer token is set in Authorization header."""
        client = _DummyOtherClient()
        client.get_contacts("mytoken")
        assert client.last_get["headers"]["Authorization"] == "Bearer mytoken"

    def test_accept_header_is_json(self) -> None:
        """Test Accept header requests JSON."""
        client = _DummyOtherClient()
        client.get_contacts("tok")
        assert client.last_get["headers"]["Accept"] == "application/json"


class TestGetContactsParams:
    """Test that get_contacts constructs correct query params."""

    def test_default_per_page_is_15(self) -> None:
        """Test default per_page sent to API is 15."""
        client = _DummyOtherClient()
        client.get_contacts("tok")
        assert client.last_get["params"]["per_page"] == 15

    def test_page_is_always_1(self) -> None:
        """Test page param is hardcoded to 1."""
        client = _DummyOtherClient()
        client.get_contacts("tok")
        assert client.last_get["params"]["page"] == 1

    def test_custom_per_page_is_forwarded(self) -> None:
        """Test custom per_page value is forwarded in params."""
        client = _DummyOtherClient()
        client.get_contacts("tok", per_page=50)
        assert client.last_get["params"]["per_page"] == 50

    def test_no_filters_param_when_query_is_none(self) -> None:
        """Test no filters key in params when query is None."""
        client = _DummyOtherClient()
        client.get_contacts("tok", query=None)
        assert "filters" not in client.last_get["params"]

    def test_no_filters_param_when_query_is_empty_string(self) -> None:
        """Test no filters key in params when query is empty string."""
        client = _DummyOtherClient()
        client.get_contacts("tok", query="")
        assert "filters" not in client.last_get["params"]

    def test_no_filters_param_when_query_is_whitespace(self) -> None:
        """Test no filters key in params when query is only whitespace."""
        client = _DummyOtherClient()
        client.get_contacts("tok", query="   ")
        assert "filters" not in client.last_get["params"]

    def test_filters_param_present_when_query_provided(self) -> None:
        """Test filters key is present in params when query is provided."""
        client = _DummyOtherClient()
        client.get_contacts("tok", query="john")
        assert "filters" in client.last_get["params"]


class TestGetContactsFilterShape:
    """Test that get_contacts builds the correct filter JSON."""

    def _get_filter(self, query: str) -> list:
        """Helper to get parsed filters for a given query."""
        client = _DummyOtherClient()
        client.get_contacts("tok", query=query)
        return json.loads(client.last_get["params"]["filters"])

    def test_filter_is_list_with_one_or_object(self) -> None:
        """Test top-level filter is a list wrapping a single _OR object."""
        filters = self._get_filter("john")
        assert isinstance(filters, list)
        assert len(filters) == 1
        assert "_OR" in filters[0]

    def test_or_contains_five_clauses(self) -> None:
        """Test _OR combinator contains exactly 5 field clauses."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        assert len(or_clauses) == 5

    def test_query_value_passed_without_wildcards(self) -> None:
        """Test query value is passed raw without % wrapping."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        for clause in or_clauses:
            field = list(clause.keys())[0]
            if field != "_OR":
                assert clause[field]["value"] == "john"

    def test_email_clause_uses_like_type(self) -> None:
        """Test email filter clause uses 'like' type."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        email_clause = next(c for c in or_clauses if "email" in c)
        assert email_clause["email"]["type"] == "like"
        assert email_clause["email"]["value"] == "john"

    def test_first_name_clause_present(self) -> None:
        """Test first_name filter clause is present."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        assert any("first_name" in c for c in or_clauses)

    def test_last_name_clause_present(self) -> None:
        """Test last_name filter clause is present."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        assert any("last_name" in c for c in or_clauses)

    def test_full_name_clause_present(self) -> None:
        """Test full_name filter clause is present."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        assert any("full_name" in c for c in or_clauses)

    def test_phone_clause_present(self) -> None:
        """Test phone filter clause is present."""
        filters = self._get_filter("john")
        or_clauses = filters[0]["_OR"]
        assert any("phone" in c for c in or_clauses)

    def test_query_whitespace_is_stripped(self) -> None:
        """Test surrounding whitespace is stripped from query before building filter."""
        client = _DummyOtherClient()
        client.get_contacts("tok", query="  john  ")
        filters = json.loads(client.last_get["params"]["filters"])
        or_clauses = filters[0]["_OR"]
        email_clause = next(c for c in or_clauses if "email" in c)
        assert email_clause["email"]["value"] == "john"

    @pytest.mark.parametrize("field", ["first_name", "last_name", "full_name", "phone"])
    def test_field_clause_value_matches_query(self, field: str) -> None:
        """Test each field clause carries the stripped query value."""
        filters = self._get_filter("kucher")
        or_clauses = filters[0]["_OR"]
        clause = next(c for c in or_clauses if field in c)
        assert clause[field]["value"] == "kucher"
        assert clause[field]["type"] == "like"


class TestGetContactsReturnType:
    """Test that get_contacts returns the validated model."""

    def test_returns_crm_contacts_response(self) -> None:
        """Test return value is a CrmContactsResponse instance."""
        client = _DummyOtherClient()
        result = client.get_contacts("tok")
        assert isinstance(result, CrmContactsResponse)

    def test_returns_empty_data_when_no_contacts(self) -> None:
        """Test empty data list is returned when API has no contacts."""
        client = _DummyOtherClient()
        result = client.get_contacts("tok")
        assert result.data == []
