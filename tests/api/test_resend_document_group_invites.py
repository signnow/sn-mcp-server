"""API-level tests for SignNowAPIClient.resend_document_group_invites."""

from __future__ import annotations

import json

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import ResendDocumentGroupInvitesRequest


class TestResendDocumentGroupInvites:
    """Verify client.resend_document_group_invites builds the correct HTTP request and handles responses."""

    def test_success_builds_post_request(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /documentgroup/{id}/groupinvite/{invite_id}/resendinvites → 200 → returns True."""
        # ARRANGE
        route = mock_api.post("/documentgroup/dg_001/groupinvite/ginv_001/resendinvites").respond(200)

        # ACT
        result = client.resend_document_group_invites(
            token=token,
            document_group_id="dg_001",
            group_invite_id="ginv_001",
            request_data=ResendDocumentGroupInvitesRequest(email="signer@example.com", client_timestamp=1780388009),
        )

        # ASSERT — return value
        assert result is True

        # ASSERT — request built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/documentgroup/dg_001/groupinvite/ginv_001/resendinvites"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"

        body = json.loads(request.content)
        assert body == {"email": "signer@example.com", "client_timestamp": 1780388009}

    def test_success_with_no_content_response(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """204 No Content → still returns True (no body to parse)."""
        # ARRANGE
        route = mock_api.post("/documentgroup/dg_001/groupinvite/ginv_001/resendinvites").respond(204)

        # ACT
        result = client.resend_document_group_invites(
            token=token,
            document_group_id="dg_001",
            group_invite_id="ginv_001",
            request_data=ResendDocumentGroupInvitesRequest(email="signer@example.com", client_timestamp=1780388009),
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
        route = mock_api.post("/documentgroup/dg_001/groupinvite/ginv_001/resendinvites").respond(403, json={"403": "forbidden"})

        # ACT & ASSERT
        with pytest.raises(SignNowAPIError) as exc_info:
            client.resend_document_group_invites(
                token=token,
                document_group_id="dg_001",
                group_invite_id="ginv_001",
                request_data=ResendDocumentGroupInvitesRequest(email="signer@example.com", client_timestamp=1780388009),
            )

        assert route.called
        assert exc_info.value.status_code == 403
