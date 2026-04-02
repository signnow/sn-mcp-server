"""
API-level test fixtures — client wired to the shared respx mock.

API tests validate SignNowAPIClient methods directly: client method → HTTP request
construction → response parsing / error handling.

mock_api and load_fixture are provided by tests/conftest.py.
"""

from __future__ import annotations

import pytest
import respx
from pydantic import AnyHttpUrl

from signnow_client import SignNowAPIClient
from signnow_client.config import SignNowConfig

FAKE_TOKEN = "api-test-token"  # noqa: S105
FAKE_API_BASE = "https://api-eval.signnow.com"  # must match tests/conftest.py


@pytest.fixture()
def client(mock_api: respx.MockRouter) -> SignNowAPIClient:
    """Real SignNowAPIClient pointing at the mock base URL.

    mock_api is declared as a parameter so pytest activates the respx interceptor
    before the client is constructed.
    basic_token=None suppresses the @model_validator that requires real credentials.
    """
    cfg = SignNowConfig.model_construct(
        api_base=AnyHttpUrl(FAKE_API_BASE),
        app_base=AnyHttpUrl("https://app.signnow.com"),
        client_id="test_client_id",
        client_secret="test_client_secret",  # noqa: S106
        basic_token=None,
        user_email=None,
        password=None,
        default_scope="*",
    )
    return SignNowAPIClient(cfg)


@pytest.fixture()
def token() -> str:
    """Standard bearer token for all API tests."""
    return FAKE_TOKEN
