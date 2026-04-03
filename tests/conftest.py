"""Shared fixtures for all test layers (unit, integration, api)."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest
import respx

FAKE_API_BASE = "https://api-eval.signnow.com"


@pytest.fixture()
def mock_api() -> Generator[respx.MockRouter, None, None]:
    """Intercept all httpx traffic with respx. Add routes per-test."""
    with respx.mock(base_url=FAKE_API_BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture()
def load_fixture(request: pytest.FixtureRequest) -> Callable[[str], dict[str, Any]]:
    """Return a fixture loader for the calling test's own fixtures/ directory.

    Resolves the path relative to the test file — not this conftest — so
    tests/api/ and tests/integration/ each load from their own fixtures/
    subdirectory without hard-coding the path here.

    Delegating via a returned function allows per-class fixture override
    (a test class can shadow load_fixture to inject field transformations).
    """
    fixtures_dir = request.path.parent / "fixtures"

    def _load(name: str) -> dict[str, Any]:
        path = fixtures_dir / f"{name}.json"
        data = json.loads(path.read_text())
        assert isinstance(data, dict), f"Fixture {name!r} must be a JSON object, got {type(data).__name__}"
        return cast(dict[str, Any], data)

    return _load
