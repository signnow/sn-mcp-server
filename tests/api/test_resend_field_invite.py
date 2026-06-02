"""API-level tests for SignNowAPIClient.resend_field_invite."""

from __future__ import annotations

import json

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.templates_and_documents import ResendFieldInviteRequest


class TestResendFieldInvite:
    """Verify client.resend_field_invite builds the correct HTTP request and handles responses."""

    def test_success_builds_put_request(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """PUT /fieldinvite/{id}/resend with client_timestamp → 200 → returns True."""
        # ARRANGE
        route = mock_api.put("/fieldinvite/fi_001/resend").respond(200)

        # ACT
        result = client.resend_field_invite(
            token=token,
            field_invite_id="fi_001",
            request_data=ResendFieldInviteRequest(client_timestamp=1780388421),
        )

        # ASSERT — return value
        assert result is True

        # ASSERT — request built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "PUT"
        assert request.url.path == "/fieldinvite/fi_001/resend"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"

        body = json.loads(request.content)
        assert body == {"client_timestamp": 1780388421}

    def test_success_with_no_content_response(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """204 No Content → still returns True (no body to parse)."""
        # ARRANGE
        route = mock_api.put("/fieldinvite/fi_001/resend").respond(204)

        # ACT
        result = client.resend_field_invite(
            token=token,
            field_invite_id="fi_001",
            request_data=ResendFieldInviteRequest(client_timestamp=1780388421),
        )

        # ASSERT
        assert result is True
        assert route.called

    def test_api_error_raises_signnow_api_error(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """Non-2xx response → SignNowAPIError with the right status code."""
        # ARRANGE
        route = mock_api.put("/fieldinvite/fi_001/resend").respond(404, json={"404": "not found"})

        # ACT & ASSERT
        with pytest.raises(SignNowAPIError) as exc_info:
            client.resend_field_invite(
                token=token,
                field_invite_id="fi_001",
                request_data=ResendFieldInviteRequest(client_timestamp=1780388421),
            )

        assert route.called
        assert exc_info.value.status_code == 404

    def test_429_parses_retry_after_header(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """429 with a numeric Retry-After header → error.retry_after holds the delay in seconds."""
        # ARRANGE
        mock_api.put("/fieldinvite/fi_001/resend").respond(429, headers={"Retry-After": "7"}, json={"error": "Too Many Attempts."})

        # ACT & ASSERT
        with pytest.raises(SignNowAPIError) as exc_info:
            client.resend_field_invite(
                token=token,
                field_invite_id="fi_001",
                request_data=ResendFieldInviteRequest(client_timestamp=1780388421),
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 7.0

    def test_error_without_retry_after_header_leaves_it_none(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """A 429 with no Retry-After header → error.retry_after is None (caller falls back to backoff)."""
        # ARRANGE
        mock_api.put("/fieldinvite/fi_001/resend").respond(429, json={"error": "Too Many Attempts."})

        # ACT & ASSERT
        with pytest.raises(SignNowAPIError) as exc_info:
            client.resend_field_invite(
                token=token,
                field_invite_id="fi_001",
                request_data=ResendFieldInviteRequest(client_timestamp=1780388421),
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is None
