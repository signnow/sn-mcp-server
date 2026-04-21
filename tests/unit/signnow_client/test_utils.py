"""Unit tests for signnow_client.utils helpers."""

from __future__ import annotations

import pytest

from signnow_client.utils import decode_basic_auth, encode_basic_auth, validate_token_response


class TestEncodeDecodeRoundtrip:
    def test_encode_then_decode_returns_original(self) -> None:
        token = encode_basic_auth("client-id-123", "client-secret-xyz")
        cid, csec = decode_basic_auth(token)
        assert cid == "client-id-123"
        assert csec == "client-secret-xyz"


class TestDecodeBasicAuthErrors:
    def test_raises_value_error_for_garbage_input(self) -> None:
        """Non-base64 input should surface as ValueError with a clear message."""
        with pytest.raises(ValueError, match="Invalid Basic Auth token format"):
            decode_basic_auth("!!!not-valid-base64!!!")


class TestValidateTokenResponse:
    def test_returns_true_for_complete_response(self) -> None:
        assert validate_token_response({"access_token": "a", "token_type": "Bearer"}) is True

    def test_returns_false_when_access_token_missing(self) -> None:
        assert validate_token_response({"token_type": "Bearer"}) is False
