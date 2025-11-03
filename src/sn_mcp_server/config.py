from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OAuth server configuration (optional with sensible default)
    oauth_issuer: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000"),
        description="OAuth issuer URL",
        alias="OAUTH_ISSUER",
    )
    access_ttl: int = Field(default=3600, description="Access token TTL in seconds", alias="ACCESS_TTL")
    refresh_ttl: int = Field(default=2592000, description="Refresh token TTL in seconds", alias="REFRESH_TTL")  # 30 days
    allowed_redirects: str = Field(default="http://localhost,http://127.0.0.1", description="Comma-separated list of allowed redirect URIs", alias="ALLOWED_REDIRECTS")

    # OAuth RSA key configuration
    oauth_rsa_private_pem: str | None = Field(default=None, description="OAuth RSA private key in PEM format", alias="OAUTH_RSA_PRIVATE_PEM")
    oauth_jwk_kid: str = Field(default="mcp-dev-key", description="OAuth JWK key ID", alias="OAUTH_JWK_KID")

    @field_validator("oauth_issuer", mode="before")
    @classmethod
    def validate_oauth_issuer(cls: type["Settings"], v: str | None) -> AnyHttpUrl:
        """Handle empty string for oauth_issuer"""
        if v == "" or v is None:
            return AnyHttpUrl("http://localhost:8000")
        return v

    @field_validator("access_ttl", mode="before")
    @classmethod
    def validate_access_ttl(cls: type["Settings"], v: str | None) -> int:
        """Handle empty string for access_ttl"""
        if v == "" or v is None:
            return 3600
        return v

    @field_validator("refresh_ttl", mode="before")
    @classmethod
    def validate_refresh_ttl(cls: type["Settings"], v: str | None) -> int:
        """Handle empty string for refresh_ttl"""
        if v == "" or v is None:
            return 2592000
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

    @property
    def effective_resource_http_url(self: "Settings") -> str:
        """Get resource HTTP URL, auto-generated from oauth_issuer"""
        if not self.oauth_issuer:
            raise ValueError("OAUTH_ISSUER is required to generate resource URLs")
        return f"{str(self.oauth_issuer).rstrip('/')}/mcp"

    @property
    def effective_resource_sse_url(self: "Settings") -> str:
        """Get resource SSE URL, auto-generated from oauth_issuer"""
        if not self.oauth_issuer:
            raise ValueError("OAUTH_ISSUER is required to generate resource URLs")
        return f"{str(self.oauth_issuer).rstrip('/')}/sse"

    def get_rsa_private_key(self: "Settings") -> rsa.RSAPrivateKey:
        """Get RSA private key - either from config or generate new one"""
        if self.oauth_rsa_private_pem:
            try:
                key = serialization.load_pem_private_key(self.oauth_rsa_private_pem.encode(), password=None)
                if isinstance(key, rsa.RSAPrivateKey):
                    return key
            except ValueError:
                pass

        # Generate new key if loading failed or no key provided
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)


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

    # Get field aliases (which are the env variable names)
    secret_fields = {"OAUTH_RSA_PRIVATE_PEM"}

    # Use model_dump with by_alias=True to get values by their env var names
    config_dict = settings.model_dump(by_alias=True)

    # Print all config values using their aliases (env var names)
    for env_var_name, value in sorted(config_dict.items()):
        if value is None:
            print(f"  {env_var_name}=<not set>")
        else:
            if env_var_name in secret_fields:
                str_value = str(value)
                masked = _mask_secret_value(str_value)
                print(f"  {env_var_name}={masked}")
            else:
                print(f"  {env_var_name}={value}")

    print("=" * 80)


def load_settings() -> Settings:
    settings = Settings()
    _print_config_values(settings)
    return settings
