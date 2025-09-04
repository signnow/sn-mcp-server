"""
SignNow API Configuration

Configuration settings for the SignNow API client.
"""

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SignNowConfig(BaseSettings):
    """Configuration for SignNow API client"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API endpoints
    api_base: AnyHttpUrl = Field(default_factory=lambda: AnyHttpUrl("https://api.signnow.com"), description="SignNow API base URL", alias="SIGNNOW_API_BASE")
    app_base: AnyHttpUrl = Field(default_factory=lambda: AnyHttpUrl("https://app.signnow.com"), description="SignNow app base URL", alias="SIGNNOW_APP_BASE")

    # OAuth2 credentials
    client_id: str = Field(description="SignNow client ID", alias="SIGNNOW_CLIENT_ID")
    client_secret: str = Field(description="SignNow client secret", alias="SIGNNOW_CLIENT_SECRET")
    basic_token: str = Field(description="SignNow API basic token", alias="SIGNNOW_API_BASIC_TOKEN")

    # User credentials (for password grant)
    user_email: str = Field(description="SignNow user email", alias="SIGNNOW_USER_EMAIL")
    password: str = Field(description="SignNow user password", alias="SIGNNOW_PASSWORD")

    # Default scope
    default_scope: str = Field(default="*", description="Default OAuth scope")


def load_signnow_config() -> SignNowConfig:
    """Load SignNow configuration from environment variables"""
    return SignNowConfig()
