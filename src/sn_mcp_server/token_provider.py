from __future__ import annotations

from fastmcp.server.auth import AccessToken, TokenVerifier

from signnow_client import SignNowAPIClient
from signnow_client.config import load_signnow_config

from .config import load_settings


class SignNowTokenVerifier(TokenVerifier):
    """Minimal token verifier for opaque SignNow access tokens.

    OAuthProxy already handles token storage, expiry checks, and obtains
    tokens from valid exchanges.  The verifier simply wraps the upstream
    token so that FastMCP can pass it through to tool handlers.
    """

    async def verify_token(self, token: str) -> AccessToken | None:  # noqa: ANN401
        if not token:
            return None
        return AccessToken(token=token, client_id="signnow", scopes=["*"])


class TokenProvider:
    """Provides access tokens from config credentials (STDIO / dev mode)."""

    def __init__(self) -> None:
        self.settings = load_settings()
        self.signnow_config = load_signnow_config()
        self.signnow_client = SignNowAPIClient(self.signnow_config)

    def get_access_token(self) -> str | None:
        """Get access token from config credentials (password grant).

        Returns:
            Access token string or None if unable to get token
        """
        if self.has_config_credentials():
            return self._get_token_from_config()
        return None

    def has_config_credentials(self) -> bool:
        """Check if username and password are configured"""
        return bool(self.signnow_config.user_email and self.signnow_config.password and self.signnow_config.basic_token)

    def get_token_from_headers(self, headers: dict[str, str] | object) -> str | None:
        """Extract Bearer token from Authorization header.

        Args:
            headers: Request headers (e.g. request.headers or dict)

        Returns:
            Token string or None if missing/invalid
        """
        get = getattr(headers, "get", None)
        if get is None:
            return None
        auth = get("authorization") or get("Authorization")
        if not auth or not isinstance(auth, str):
            return None
        auth = auth.strip()
        if not auth.lower().startswith("bearer ") or len(auth) <= 7:
            return None
        return auth[7:].strip()

    def _get_token_from_config(self) -> str | None:
        """Get token using configured username and password"""
        response = self.signnow_client.get_tokens_by_password(username=self.signnow_config.user_email, password=self.signnow_config.password)

        if response and isinstance(response, dict) and "access_token" in response:
            token = response["access_token"]
            if isinstance(token, str):
                return token

        return None
