"""Unit tests for SignNowAPIClientBase._post timeout parameter."""

from __future__ import annotations

from unittest.mock import MagicMock

from signnow_client.client_base import SignNowAPIClientBase
from signnow_client.config import SignNowConfig


def _make_client(http: MagicMock) -> SignNowAPIClientBase:
    cfg = SignNowConfig.model_construct()
    return SignNowAPIClientBase(cfg, client=http)


def _make_http_response(status_code: int = 200, json_body: dict[str, str] | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.content = b'{"ok":true}' if json_body is None else b'{"k":"v"}'
    response.json.return_value = json_body if json_body is not None else {"ok": True}
    response.raise_for_status.return_value = None
    return response


class TestPostTimeout:
    def test_passes_timeout_kwarg_when_provided(self) -> None:
        http = MagicMock()
        http.post.return_value = _make_http_response()
        client = _make_client(http)

        client._post("/v2/anything", headers={"x": "y"}, json_data={"a": 1}, timeout=30.0)

        http.post.assert_called_once()
        assert http.post.call_args.kwargs["timeout"] == 30.0

    def test_omits_timeout_kwarg_when_none(self) -> None:
        http = MagicMock()
        http.post.return_value = _make_http_response()
        client = _make_client(http)

        client._post("/v2/anything", headers={"x": "y"}, json_data={"a": 1})

        http.post.assert_called_once()
        assert "timeout" not in http.post.call_args.kwargs
