"""
API-level tests for SignNowAPIClient.update_document_group_invite_step.

Tests validate HTTP method, URL, headers, request body construction,
and response/error handling.
HTTP layer is mocked via respx; no real network calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models import UpdateDocGroupInviteStepRequest
from signnow_client.models.document_groups import (
    UpdateDocGroupInviteActionAttributes,
    UpdateDocGroupInviteEmail,
)

_DOC_GROUP_ID = "dg-001"
_INVITE_ID = "inv-001"
_STEP_ID = "step-001"
_DOC_ID = "doc-001"
_CURRENT_EMAIL = "old@example.com"
_NEW_EMAIL = "new@example.com"

_EXPECTED_URL = f"/documentgroup/{_DOC_GROUP_ID}/groupinvite/{_INVITE_ID}/invitestep/{_STEP_ID}/update"


def _make_request() -> UpdateDocGroupInviteStepRequest:
    """Build a minimal UpdateDocGroupInviteStepRequest for test use."""
    return UpdateDocGroupInviteStepRequest(
        user_to_update=_CURRENT_EMAIL,
        invite_email=UpdateDocGroupInviteEmail(email=_NEW_EMAIL),
        update_invite_action_attributes=[
            UpdateDocGroupInviteActionAttributes(document_id=_DOC_ID),
        ],
        replace_with_this_user=_NEW_EMAIL,
    )


class TestUpdateDocumentGroupInviteStep:
    """Verify client.update_document_group_invite_step builds correct POST request."""

    def test_correct_url_and_method(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST to /documentgroup/{id}/groupinvite/{inv_id}/invitestep/{step_id}/update."""
        # ARRANGE
        route = mock_api.post(_EXPECTED_URL).respond(200, json={})

        # ACT
        client.update_document_group_invite_step(
            token=token,
            document_group_id=_DOC_GROUP_ID,
            invite_id=_INVITE_ID,
            step_id=_STEP_ID,
            request_data=_make_request(),
        )

        # ASSERT
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == _EXPECTED_URL

    def test_authorization_header_sent(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """Bearer token is sent in Authorization header."""
        # ARRANGE
        route = mock_api.post(_EXPECTED_URL).respond(200, json={})

        # ACT
        client.update_document_group_invite_step(
            token=token,
            document_group_id=_DOC_GROUP_ID,
            invite_id=_INVITE_ID,
            step_id=_STEP_ID,
            request_data=_make_request(),
        )

        # ASSERT
        request = route.calls.last.request
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"

    def test_request_body_shape(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """Request body contains user_to_update, invite_email, update_invite_action_attributes, replace_with_this_user."""
        # ARRANGE
        route = mock_api.post(_EXPECTED_URL).respond(200, json={})

        # ACT
        client.update_document_group_invite_step(
            token=token,
            document_group_id=_DOC_GROUP_ID,
            invite_id=_INVITE_ID,
            step_id=_STEP_ID,
            request_data=_make_request(),
        )

        # ASSERT
        body = json.loads(route.calls.last.request.content)
        assert body["user_to_update"] == _CURRENT_EMAIL
        assert body["replace_with_this_user"] == _NEW_EMAIL
        assert body["invite_email"]["email"] == _NEW_EMAIL
        assert len(body["update_invite_action_attributes"]) == 1
        assert body["update_invite_action_attributes"][0]["document_id"] == _DOC_ID

    def test_optional_fields_excluded_when_none(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """Optional fields (reminder, expiration_days, etc.) are not sent when None."""
        # ARRANGE
        route = mock_api.post(_EXPECTED_URL).respond(200, json={})

        # ACT
        client.update_document_group_invite_step(
            token=token,
            document_group_id=_DOC_GROUP_ID,
            invite_id=_INVITE_ID,
            step_id=_STEP_ID,
            request_data=_make_request(),
        )

        # ASSERT
        body = json.loads(route.calls.last.request.content)
        invite_email = body["invite_email"]
        assert "reminder" not in invite_email
        assert "expiration_days" not in invite_email
        action = body["update_invite_action_attributes"][0]
        assert "allow_reassign" not in action
        assert "decline_by_signature" not in action

    def test_success_returns_true(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """200 response → method returns True."""
        # ARRANGE
        mock_api.post(_EXPECTED_URL).respond(200, json={})

        # ACT
        result = client.update_document_group_invite_step(
            token=token,
            document_group_id=_DOC_GROUP_ID,
            invite_id=_INVITE_ID,
            step_id=_STEP_ID,
            request_data=_make_request(),
        )

        # ASSERT
        assert result is True

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST → 404 → SignNowAPINotFoundError raised."""
        # ARRANGE
        error_fixture = load_fixture("error__document_group_not_found")
        mock_api.post(_EXPECTED_URL).respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.update_document_group_invite_step(
                token=token,
                document_group_id=_DOC_GROUP_ID,
                invite_id=_INVITE_ID,
                step_id=_STEP_ID,
                request_data=_make_request(),
            )
