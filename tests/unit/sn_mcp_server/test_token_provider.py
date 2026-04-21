"""Unit tests for TokenProvider._get_token_from_config.

Constructs the provider without running __init__ (which pulls real config
and an API client) and exercises the three branches of the private token
fetch: full success, malformed response, and the defensive missing-creds
precondition.
"""

from __future__ import annotations

from types import SimpleNamespace

from sn_mcp_server.token_provider import TokenProvider


def _make_provider(*, email: str | None, pwd: str | None, api_response: dict[str, str] | None) -> TokenProvider:
    """Build a TokenProvider bypassing __init__ to avoid real config load."""
    provider = object.__new__(TokenProvider)
    provider.signnow_config = SimpleNamespace(user_email=email, password=pwd, basic_token="b")  # noqa: S106
    provider.signnow_client = SimpleNamespace(get_tokens_by_password=lambda **_: api_response)
    return provider


class TestGetTokenFromConfigHappy:
    def test_returns_access_token_when_response_is_well_formed(self) -> None:
        provider = _make_provider(email="u@e.com", pwd="pw", api_response={"access_token": "tkn123"})  # noqa: S106
        assert provider._get_token_from_config() == "tkn123"


class TestGetTokenFromConfigMalformed:
    def test_returns_none_when_response_lacks_access_token(self) -> None:
        provider = _make_provider(email="u@e.com", pwd="pw", api_response={"error": "nope"})  # noqa: S106
        assert provider._get_token_from_config() is None


class TestGetTokenFromConfigMissingCredentials:
    def test_returns_none_when_email_missing(self) -> None:
        provider = _make_provider(email=None, pwd="pw", api_response=None)  # noqa: S106
        assert provider._get_token_from_config() is None

    def test_returns_none_when_password_missing(self) -> None:
        provider = _make_provider(email="u@e.com", pwd=None, api_response=None)
        assert provider._get_token_from_config() is None
