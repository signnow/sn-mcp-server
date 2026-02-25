"""Unit tests for _CORSMiddlewareWithExposeInPreflight in app module."""

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from sn_mcp_server.app import _CORSMiddlewareWithExposeInPreflight

_ORIGIN = "https://claude.ai"
_PREFLIGHT_HEADERS = {
    "Origin": _ORIGIN,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type,authorization,mcp-session-id",
}


def _make_app(expose_headers: list[str]) -> TestClient:
    async def _handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    app = Starlette()
    app.add_middleware(
        _CORSMiddlewareWithExposeInPreflight,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=expose_headers,
        allow_credentials=True,
    )
    app.add_route("/mcp", _handler, methods=["OPTIONS", "POST", "GET"])
    return TestClient(app, raise_server_exceptions=True)


class TestCORSExposeHeadersPreflight:
    """Regression tests for Access-Control-Expose-Headers in OPTIONS preflight responses."""

    def test_preflight_includes_expose_header(self) -> None:
        """OPTIONS response must carry Access-Control-Expose-Headers: Mcp-Session-Id."""
        client = _make_app(["Mcp-Session-Id"])
        resp = client.options("/mcp", headers=_PREFLIGHT_HEADERS)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-expose-headers") == "Mcp-Session-Id"

    def test_actual_response_includes_expose_header(self) -> None:
        """Non-preflight POST response must also carry Access-Control-Expose-Headers."""
        client = _make_app(["Mcp-Session-Id"])
        resp = client.post("/mcp", headers={"Origin": _ORIGIN})
        assert resp.headers.get("access-control-expose-headers") == "Mcp-Session-Id"

    def test_expose_header_absent_when_empty_list(self) -> None:
        """When expose_headers=[], Access-Control-Expose-Headers must not be present."""
        client = _make_app([])
        resp = client.options("/mcp", headers=_PREFLIGHT_HEADERS)
        assert "access-control-expose-headers" not in resp.headers

    def test_preflight_echoes_request_origin_with_credentials(self) -> None:
        """With allow_credentials=True the preflight must echo the exact request origin."""
        client = _make_app(["Mcp-Session-Id"])
        resp = client.options("/mcp", headers=_PREFLIGHT_HEADERS)
        assert resp.headers.get("access-control-allow-origin") == _ORIGIN
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_multiple_expose_headers(self) -> None:
        """Multiple expose_headers values are joined with ', ' in the preflight."""
        client = _make_app(["Mcp-Session-Id", "X-Custom-Header"])
        resp = client.options("/mcp", headers=_PREFLIGHT_HEADERS)
        expose = resp.headers.get("access-control-expose-headers", "")
        assert "Mcp-Session-Id" in expose
        assert "X-Custom-Header" in expose

    def test_preflight_returns_200(self) -> None:
        """Preflight response status must be 200 OK."""
        client = _make_app(["Mcp-Session-Id"])
        resp = client.options("/mcp", headers=_PREFLIGHT_HEADERS)
        assert resp.status_code == 200

    def test_max_age_present_in_preflight(self) -> None:
        """access-control-max-age must be set in preflight response."""
        client = _make_app(["Mcp-Session-Id"])
        resp = client.options("/mcp", headers=_PREFLIGHT_HEADERS)
        assert resp.headers.get("access-control-max-age") == "600"
