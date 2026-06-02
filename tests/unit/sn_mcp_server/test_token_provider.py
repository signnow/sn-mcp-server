"""Unit tests for TokenProvider token-acquisition paths.

Constructs the provider without running __init__ (which pulls real config
and an API client) and exercises: the static token shortcut, the three
branches of the password-grant fetch, and header extraction fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sn_mcp_server.token_provider import TokenProvider


def _make_provider(*, email: str | None, pwd: str | None, api_response: dict[str, str] | None) -> TokenProvider:
    """Build a TokenProvider bypassing __init__ to avoid real config load."""
    provider = object.__new__(TokenProvider)
    provider.signnow_config = SimpleNamespace(user_email=email, password=pwd, basic_token="b")  # noqa: S106
    provider.signnow_client = SimpleNamespace(get_tokens_by_password=lambda **_: api_response)
    return provider


def _make_provider_with_static_token(
    *,
    access_token: str | None,
    email: str | None = None,
    pwd: str | None = None,
    api_response: dict[str, str] | None = None,
) -> TokenProvider:
    """Build a TokenProvider with access_token wired for get_access_token() tests."""
    provider = object.__new__(TokenProvider)
    provider.signnow_config = SimpleNamespace(
        access_token=access_token,
        user_email=email,
        password=pwd,
        basic_token="b" if (email and pwd) else None,  # noqa: S106
    )
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


class TestGetAccessTokenStaticToken:
    """Test the static token shortcut in get_access_token."""

    def test_returns_static_token_directly(self) -> None:
        """Static token is returned immediately without any OAuth call."""
        provider = _make_provider_with_static_token(access_token="my_static_token")  # noqa: S106
        assert provider.get_access_token() == "my_static_token"

    def test_static_token_wins_over_password_grant_credentials(self) -> None:
        """When both static token and password grant creds are set, static token wins."""
        provider = _make_provider_with_static_token(
            access_token="static_tok",  # noqa: S106
            email="u@e.com",
            pwd="pw",  # noqa: S106
            api_response={"access_token": "oauth_tok"},
        )
        assert provider.get_access_token() == "static_tok"

    def test_static_token_wins_over_authorization_header(self) -> None:
        """Static token wins even when a Bearer token is supplied in request headers."""
        provider = _make_provider_with_static_token(access_token="static_tok")  # noqa: S106
        assert provider.get_access_token({"authorization": "Bearer header_tok"}) == "static_tok"

    def test_falls_through_to_password_grant_when_no_static_token(self) -> None:
        """No static token → password grant path is used when credentials are present."""
        provider = _make_provider_with_static_token(
            access_token=None,
            email="u@e.com",
            pwd="pw",  # noqa: S106
            api_response={"access_token": "oauth_tok"},
        )
        assert provider.get_access_token() == "oauth_tok"

    def test_falls_through_to_headers_when_no_static_token_or_credentials(self) -> None:
        """No static token and no creds → token is extracted from the Authorization header."""
        provider = _make_provider_with_static_token(access_token=None)
        assert provider.get_access_token({"authorization": "Bearer header_tok"}) == "header_tok"

    def test_returns_none_when_all_sources_absent(self) -> None:
        """Returns None when static token, credentials, and headers are all absent."""
        provider = _make_provider_with_static_token(access_token=None)
        assert provider.get_access_token() is None


class TestSignNowAccessTokenHeader:
    """Per-request X-SignNow-Access-Token header (HTTP transport, raw SignNow token).

    Pins the FULL precedence ladder. The first row is the precedence decision made
    explicit: env static token (Option C) still wins over the per-request header.
    Flipping that single expected value (and test_static_token_wins_over_authorization_header)
    is the only change needed to switch to a "per-request wins" policy.
    """

    @pytest.mark.parametrize(
        ("static", "creds_response", "headers", "expected"),
        [
            # env static token beats the new header — preserves the Option C invariant
            ("static_tok", None, {"x-signnow-access-token": "hdr_tok", "authorization": "Bearer auth_tok"}, "static_tok"),
            # password grant beats the new header
            (None, "oauth_tok", {"x-signnow-access-token": "hdr_tok"}, "oauth_tok"),
            # dedicated header beats the generic Authorization bearer
            (None, None, {"x-signnow-access-token": "hdr_tok", "authorization": "Bearer auth_tok"}, "hdr_tok"),
            # raw token returned verbatim — no "Bearer " stripping
            (None, None, {"x-signnow-access-token": "raw_sn_tok"}, "raw_sn_tok"),
            # whitespace-only header is ignored, falls through to Authorization
            (None, None, {"x-signnow-access-token": "   ", "authorization": "Bearer auth_tok"}, "auth_tok"),
        ],
    )
    def test_signnow_token_header_precedence(
        self,
        static: str | None,
        creds_response: str | None,
        headers: dict[str, str],
        expected: str,
    ) -> None:
        provider = _make_provider_with_static_token(
            access_token=static,
            email="u@e.com" if creds_response else None,
            pwd="pw" if creds_response else None,  # noqa: S106
            api_response={"access_token": creds_response} if creds_response else None,
        )
        assert provider.get_access_token(headers) == expected

    def test_header_only_request_yields_token_for_presence_gate(self) -> None:
        """The /mcp 401 gate (auth.py) calls get_access_token(dict(request.headers)).

        A request carrying only X-SignNow-Access-Token (no config creds) must yield a
        token so the gate admits it — this is what lets a bring-your-own-token caller
        reach the tools over HTTP.
        """
        provider = _make_provider_with_static_token(access_token=None)
        assert provider.get_access_token({"x-signnow-access-token": "tenant_tok"}) == "tenant_tok"
