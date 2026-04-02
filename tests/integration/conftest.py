"""
Shared fixtures for integration tests.

Integration tests validate the full stack from tool function → SignNowAPIClient →
HTTP request construction → response parsing, using respx to intercept httpx calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
import respx
from pydantic import AnyHttpUrl

from signnow_client import SignNowAPIClient
from signnow_client.config import SignNowConfig

FAKE_API_BASE = "https://api-eval.signnow.com"
FAKE_TOKEN = "integration-test-token"  # noqa: S105
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture file by name (without .json extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def load_fixture() -> Callable[[str], dict[str, Any]]:
    """Return the fixture loader helper.

    Usage: load_fixture("post_download_link__success")
    """
    return _load_fixture


@pytest.fixture()
def mock_api() -> Generator[respx.MockRouter, None, None]:
    """Intercept all httpx traffic with respx. Add routes per-test."""
    with respx.mock(base_url=FAKE_API_BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture()
def sn_client(mock_api: respx.MockRouter) -> SignNowAPIClient:
    """Real SignNowAPIClient pointing at the mock base URL.

    Uses model_construct to bypass SignNowConfig credential validation —
    we only need api_base to be correct; credentials are never used in HTTP calls.
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
    """Standard bearer token for all integration tests."""
    return FAKE_TOKEN
