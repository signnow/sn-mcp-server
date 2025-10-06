"""
SignNow API Configuration

Configuration settings for the SignNow API client.
"""

from pydantic import AnyHttpUrl, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SignNowConfig(BaseSettings):
    """Configuration for SignNow API client

    Required environment variables follow oneOf rule:
    - Option A (Password grant): SIGNNOW_USER_EMAIL, SIGNNOW_PASSWORD, SIGNNOW_API_BASIC_TOKEN
    - Option B (Client credentials): SIGNNOW_CLIENT_ID, SIGNNOW_CLIENT_SECRET
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API endpoints
    api_base: AnyHttpUrl = Field(default_factory=lambda: AnyHttpUrl("https://api.signnow.com"), description="SignNow API base URL", alias="SIGNNOW_API_BASE")
    app_base: AnyHttpUrl = Field(default_factory=lambda: AnyHttpUrl("https://app.signnow.com"), description="SignNow app base URL", alias="SIGNNOW_APP_BASE")

    # OAuth2 credentials (made optional; validated by oneOf rule below)
    client_id: str | None = Field(default=None, description="SignNow client ID", alias="SIGNNOW_CLIENT_ID")
    client_secret: str | None = Field(default=None, description="SignNow client secret", alias="SIGNNOW_CLIENT_SECRET")
    basic_token: str | None = Field(default=None, description="SignNow API basic token", alias="SIGNNOW_API_BASIC_TOKEN")

    # User credentials (for password grant) - optional; validated by oneOf rule
    user_email: str | None = Field(default=None, description="SignNow user email", alias="SIGNNOW_USER_EMAIL")
    password: str | None = Field(default=None, description="SignNow user password", alias="SIGNNOW_PASSWORD")

    # Default scope
    default_scope: str = Field(default="*", description="Default OAuth scope")

    @model_validator(mode="after")
    def validate_one_of_credentials(self) -> "SignNowConfig":
        """Ensure that either password grant set or client credentials set is fully provided.

        Option A (password grant): SIGNNOW_USER_EMAIL, SIGNNOW_PASSWORD, SIGNNOW_API_BASIC_TOKEN
        Option B (client credentials): SIGNNOW_CLIENT_ID, SIGNNOW_CLIENT_SECRET
        """
        has_password_grant = bool(self.user_email and self.password and self.basic_token)
        has_client_credentials = bool(self.client_id and self.client_secret)

        if not (has_password_grant or has_client_credentials):
            # Build helpful error message similar to JSON Schema oneOf
            missing_a = [
                name for name, val in (
                    ("SIGNNOW_USER_EMAIL", self.user_email),
                    ("SIGNNOW_PASSWORD", self.password),
                    ("SIGNNOW_API_BASIC_TOKEN", self.basic_token),
                )
                if not val
            ]
            missing_b = [
                name for name, val in (
                    ("SIGNNOW_CLIENT_ID", self.client_id),
                    ("SIGNNOW_CLIENT_SECRET", self.client_secret),
                )
                if not val
            ]
            detail = (
                "oneOf credential sets must be provided; "
                f"missing for Option A (password grant): {', '.join(missing_a) or 'none'}; "
                f"missing for Option B (client credentials): {', '.join(missing_b) or 'none'}"
            )
            raise ValidationError.from_exception_data(
                "SignNowConfig",
                [
                    {
                        "type": "missing",
                        "loc": ("oneOf",),
                        "msg": detail,
                        "input": None,
                    }
                ],
            )
        return self


def load_signnow_config() -> SignNowConfig:
    """Load SignNow configuration from environment variables"""
    return SignNowConfig()
