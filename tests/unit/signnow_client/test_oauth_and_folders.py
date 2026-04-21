"""Unit tests for OAuth token methods and folder-by-id on OtherClientMixin.

Covers get_tokens, refresh_tokens, get_tokens_by_password (both paths),
and get_folder_by_id — all plain thin wrappers around self._post / self._get.
"""

from __future__ import annotations

from typing import Any

import pytest

from signnow_client.client_other import OtherClientMixin


class _DummyClient(OtherClientMixin):
    """Minimal stub: records _post/_get calls, returns preset response."""

    def __init__(self, basic_token: str | None = "btok") -> None:  # noqa: S107
        self.cfg = type(
            "Cfg",
            (),
            {
                "client_id": "cid",
                "client_secret": "csec",
                "basic_token": basic_token,
                "default_scope": "*",
            },
        )()
        self.last_post: dict[str, Any] | None = None
        self.last_get: dict[str, Any] | None = None
        self._post_return: dict[str, Any] | None = {"access_token": "a", "refresh_token": "r"}

    def _post(self, url: str, headers: dict | None = None, data: dict | None = None, json_data: dict | None = None, validate_model: object = None) -> dict[str, Any] | None:
        self.last_post = {"url": url, "headers": headers, "data": data}
        return self._post_return

    def _get(self, url: str, headers: dict | None = None, params: dict | None = None, validate_model: object = None) -> Any:  # noqa: ANN401
        self.last_get = {"url": url, "headers": headers, "params": params}
        return None


class TestGetTokens:
    def test_posts_to_oauth_token_with_authorization_code_grant(self) -> None:
        client = _DummyClient()
        result = client.get_tokens("auth_code_xyz")
        assert result == {"access_token": "a", "refresh_token": "r"}
        assert client.last_post is not None
        assert client.last_post["url"] == "/oauth2/token"
        assert client.last_post["data"]["grant_type"] == "authorization_code"
        assert client.last_post["data"]["code"] == "auth_code_xyz"


class TestRefreshTokens:
    def test_posts_to_oauth_token_with_refresh_grant(self) -> None:
        client = _DummyClient()
        result = client.refresh_tokens("refresh_xyz")
        assert result == {"access_token": "a", "refresh_token": "r"}
        assert client.last_post is not None
        assert client.last_post["data"]["grant_type"] == "refresh_token"
        assert client.last_post["data"]["refresh_token"] == "refresh_xyz"  # noqa: S105


class TestGetTokensByPassword:
    def test_posts_with_basic_auth_header_and_password_grant(self) -> None:
        client = _DummyClient(basic_token="b64creds")  # noqa: S106
        result = client.get_tokens_by_password("u@example.com", "pw")
        assert result == {"access_token": "a", "refresh_token": "r"}
        assert client.last_post is not None
        assert client.last_post["headers"]["Authorization"] == "Basic b64creds"
        assert client.last_post["data"]["grant_type"] == "password"
        assert client.last_post["data"]["scope"] == "*"

    def test_raises_when_basic_token_missing(self) -> None:
        client = _DummyClient(basic_token=None)
        with pytest.raises(ValueError, match="SIGNNOW_API_BASIC_TOKEN"):
            client.get_tokens_by_password("u@example.com", "pw")


class TestGetFolderById:
    def test_omits_optional_params_when_not_provided(self) -> None:
        """params dict is empty (only defaults) when no filters are set."""
        client = _DummyClient()
        client.get_folder_by_id("ftok", "folder-1")
        assert client.last_get is not None
        # order defaults to "desc" and entity_type to "document-all"; no others.
        assert client.last_get["params"] == {"order": "desc", "entity_type": "document-all"}
