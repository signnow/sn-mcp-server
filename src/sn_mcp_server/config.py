from __future__ import annotations

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OAuth issuer / base URL for the MCP server (used by OAuthProxy)
    oauth_issuer: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000"),
        description="OAuth issuer URL / base URL for the MCP HTTP server",
        alias="OAUTH_ISSUER",
    )

    # Allowed redirect URIs (passed to OAuthProxy)
    allowed_redirects: str = Field(default="http://localhost,http://127.0.0.1", description="Comma-separated list of allowed redirect URIs", alias="ALLOWED_REDIRECTS")

    @field_validator("oauth_issuer", mode="before")
    @classmethod
    def validate_oauth_issuer(cls: type["Settings"], v: str | None) -> AnyHttpUrl:
        """Handle empty string for oauth_issuer"""
        if v == "" or v is None:
            return AnyHttpUrl("http://localhost:8000")
        return v

    @field_validator("allowed_redirects")
    @classmethod
    def validate_redirects(cls: type["Settings"], v: str) -> str:
        """Validate that all redirect URIs are valid"""
        if not v:
            return v

        uris = [uri.strip() for uri in v.split(",") if uri.strip()]
        for uri in uris:
            try:
                AnyHttpUrl(uri)
            except ValueError as e:
                raise ValueError(f"Invalid redirect URI '{uri}': {e}") from e
        return v

    @property
    def allowed_redirects_list(self: "Settings") -> list[str]:
        """Convert comma-separated redirects string to list"""
        return [uri.strip() for uri in self.allowed_redirects.split(",") if uri.strip()]


# ---------------------------------------------------------------------------
# OAuthProxy factory
# ---------------------------------------------------------------------------


def create_auth_provider(settings: Settings) -> "OAuthProxy | None":
    """Create an OAuthProxy auth provider if OAuth credentials are available.

    Returns ``None`` when config-based credentials (user/password) are present
    (STDIO / dev mode) – in that case no HTTP-level OAuth is needed because
    ``TokenProvider`` resolves tokens from config.
    """
    from fastmcp.server.auth import OAuthProxy

    from signnow_client.config import load_signnow_config

    from .token_provider import SignNowTokenVerifier

    sn = load_signnow_config()

    # If password-grant credentials are configured the server can obtain
    # SignNow tokens directly – skip OAuthProxy.
    if sn.user_email and sn.password and sn.basic_token:
        return None

    # OAuthProxy requires client_id + client_secret to talk to upstream IdP.
    if not (sn.client_id and sn.client_secret):
        return None

    base_url = str(settings.oauth_issuer).rstrip("/")

    return OAuthProxy(
        upstream_authorization_endpoint=f"{str(sn.app_base).rstrip('/')}/authorize",
        upstream_token_endpoint=f"{str(sn.api_base).rstrip('/')}/oauth2/token",
        upstream_revocation_endpoint=f"{str(sn.api_base).rstrip('/')}/oauth2/terminate",
        upstream_client_id=sn.client_id,
        upstream_client_secret=sn.client_secret,
        token_verifier=SignNowTokenVerifier(),
        base_url=base_url,
        issuer_url=base_url,
        token_endpoint_auth_method="client_secret_post",
        forward_pkce=True,
        allowed_client_redirect_uris=settings.allowed_redirects_list or None,
        require_authorization_consent=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_secret_value(value: str) -> str:
    """Mask secret values for logging"""
    if not value or len(value) < 4:
        return "***"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def _print_config_values(settings: Settings) -> None:
    """Print all config values that were loaded from environment variables"""
    print("=" * 80)
    print("Configuration values loaded from environment (sn_mcp_server):")
    print("=" * 80)

    config_dict = settings.model_dump(by_alias=True)

    for env_var_name, value in sorted(config_dict.items()):
        if value is None:
            print(f"  {env_var_name}=<not set>")
        else:
            print(f"  {env_var_name}={value}")

    print("=" * 80)


def load_settings() -> Settings:
    settings = Settings()
    _print_config_values(settings)
    return settings
