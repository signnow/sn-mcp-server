"""
API-level tests for SignNowAPIClient cancel-invite-related methods.

Tests validate HTTP method, URL, headers, and request/response handling.
HTTP layer is mocked via respx; no real network calls.

Covered methods:
- get_document_freeform_invites
- cancel_document_field_invite
- cancel_document_freeform_invite
- cancel_document_group_field_invite
- cancel_freeform_invite
- get_field_invite
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models import (
    CancelDocumentFieldInviteRequest,
    CancelDocumentFieldInviteResponse,
    CancelDocumentFreeformInviteRequest,
    CancelFreeformInviteRequest,
    GetDocumentFreeFormInvitesResponse,
    GetFieldInviteResponse,
)


class TestGetDocumentFreeformInvites:
    """Verify client.get_document_freeform_invites builds correct GET request and parses response."""

    def test_success_returns_parsed_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """GET /v2/documents/{id}/free-form-invites → 200 → GetDocumentFreeFormInvitesResponse."""
        # ARRANGE
        fixture = load_fixture("get_document_freeform_invites__success")
        route = mock_api.get("/v2/documents/doc-001/free-form-invites").respond(200, json=fixture)

        # ACT
        result = client.get_document_freeform_invites(token=token, document_id="doc-001")

        # ASSERT — response parsed
        assert isinstance(result, GetDocumentFreeFormInvitesResponse)
        assert len(result.data) == 1
        assert result.data[0].id == fixture["data"][0]["id"]
        assert result.data[0].status == fixture["data"][0]["status"]
        assert result.data[0].email == fixture["data"][0]["email"]

        # ASSERT — request built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.url.path == "/v2/documents/doc-001/free-form-invites"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["accept"] == "application/json"

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """GET /v2/documents/{id}/free-form-invites → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get("/v2/documents/doc-999/free-form-invites").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.get_document_freeform_invites(token=token, document_id="doc-999")


class TestCancelDocumentFieldInvite:
    """Verify client.cancel_document_field_invite builds correct PUT request and parses response."""

    def test_success_returns_parsed_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """PUT /document/{id}/fieldinvitecancel → 200 → CancelDocumentFieldInviteResponse."""
        # ARRANGE
        fixture = load_fixture("put_cancel_document_field_invite__success")
        route = mock_api.put("/document/doc-001/fieldinvitecancel").respond(200, json=fixture)
        request_data = CancelDocumentFieldInviteRequest(reason="No longer needed")

        # ACT
        result = client.cancel_document_field_invite(token=token, document_id="doc-001", request_data=request_data)

        # ASSERT — response parsed
        assert isinstance(result, CancelDocumentFieldInviteResponse)
        assert result.status == fixture["status"]

        # ASSERT — request built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "PUT"
        assert request.url.path == "/document/doc-001/fieldinvitecancel"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"

        body = json.loads(request.content)
        assert body["reason"] == "No longer needed"

    def test_none_reason_excluded_from_body(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """PUT /document/{id}/fieldinvitecancel with reason=None → body excludes 'reason'."""
        # ARRANGE
        fixture = load_fixture("put_cancel_document_field_invite__success")
        route = mock_api.put("/document/doc-001/fieldinvitecancel").respond(200, json=fixture)
        request_data = CancelDocumentFieldInviteRequest(reason=None)

        # ACT
        client.cancel_document_field_invite(token=token, document_id="doc-001", request_data=request_data)

        # ASSERT — reason not sent when None
        body = json.loads(route.calls.last.request.content)
        assert "reason" not in body

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """PUT /document/{id}/fieldinvitecancel → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.put("/document/doc-999/fieldinvitecancel").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.cancel_document_field_invite(
                token=token,
                document_id="doc-999",
                request_data=CancelDocumentFieldInviteRequest(),
            )


class TestCancelDocumentFreeformInvite:
    """Verify client.cancel_document_freeform_invite builds correct PUT request and returns True."""

    def test_success_returns_true(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """PUT /invite/{id}/cancel → 200 → True."""
        # ARRANGE
        route = mock_api.put("/invite/ff-invite-001/cancel").respond(200, json={})

        # ACT
        result = client.cancel_document_freeform_invite(
            token=token,
            invite_id="ff-invite-001",
            request_data=CancelDocumentFreeformInviteRequest(reason="cancelled"),
        )

        # ASSERT
        assert result is True
        assert route.called
        request = route.calls.last.request
        assert request.method == "PUT"
        assert request.url.path == "/invite/ff-invite-001/cancel"
        assert request.headers["authorization"] == f"Bearer {token}"

        body = json.loads(request.content)
        assert body["reason"] == "cancelled"

    def test_none_reason_excluded_from_body(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """PUT /invite/{id}/cancel with reason=None → body excludes 'reason'."""
        # ARRANGE
        route = mock_api.put("/invite/ff-invite-001/cancel").respond(200, json={})

        # ACT
        client.cancel_document_freeform_invite(
            token=token,
            invite_id="ff-invite-001",
            request_data=CancelDocumentFreeformInviteRequest(reason=None),
        )

        # ASSERT
        body = json.loads(route.calls.last.request.content)
        assert "reason" not in body

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """PUT /invite/{id}/cancel → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__invite_not_found")
        mock_api.put("/invite/ff-999/cancel").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.cancel_document_freeform_invite(
                token=token,
                invite_id="ff-999",
                request_data=CancelDocumentFreeformInviteRequest(),
            )


class TestCancelDocumentGroupFieldInvite:
    """Verify client.cancel_document_group_field_invite builds correct POST request and returns True."""

    def test_success_returns_true(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /documentgroup/{id}/groupinvite/{inv_id}/cancelinvite → 200 → True."""
        # ARRANGE
        route = mock_api.post("/documentgroup/dg-001/groupinvite/inv-001/cancelinvite").respond(200, json={})

        # ACT
        result = client.cancel_document_group_field_invite(
            token=token,
            document_group_id="dg-001",
            invite_id="inv-001",
        )

        # ASSERT
        assert result is True
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/documentgroup/dg-001/groupinvite/inv-001/cancelinvite"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /documentgroup/{id}/groupinvite/{inv_id}/cancelinvite → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__invite_not_found")
        mock_api.post("/documentgroup/dg-999/groupinvite/inv-999/cancelinvite").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.cancel_document_group_field_invite(
                token=token,
                document_group_id="dg-999",
                invite_id="inv-999",
            )


class TestCancelFreeformInvite:
    """Verify client.cancel_freeform_invite builds correct POST request and returns True."""

    def test_success_returns_true(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /v2/document-groups/{id}/free-form-invites/{ff_id}/cancel → 200 → True."""
        # ARRANGE
        route = mock_api.post("/v2/document-groups/dg-001/free-form-invites/ff-001/cancel").respond(200, json={})

        # ACT
        result = client.cancel_freeform_invite(
            token=token,
            document_group_id="dg-001",
            freeform_invite_id="ff-001",
            request_data=CancelFreeformInviteRequest(reason="No longer needed", client_timestamp=1700000000),
        )

        # ASSERT
        assert result is True
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/v2/document-groups/dg-001/free-form-invites/ff-001/cancel"
        assert request.headers["authorization"] == f"Bearer {token}"

        body = json.loads(request.content)
        assert body["reason"] == "No longer needed"
        assert body["client_timestamp"] == 1700000000

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST .../cancel → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__invite_not_found")
        mock_api.post("/v2/document-groups/dg-999/free-form-invites/ff-999/cancel").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.cancel_freeform_invite(
                token=token,
                document_group_id="dg-999",
                freeform_invite_id="ff-999",
                request_data=CancelFreeformInviteRequest(client_timestamp=1700000000),
            )


class TestGetFieldInvite:
    """Verify client.get_field_invite builds correct GET request and parses response."""

    def test_success_returns_parsed_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """GET /documentgroup/{id}/groupinvite/{inv_id} → 200 → GetFieldInviteResponse."""
        # ARRANGE
        fixture = load_fixture("get_field_invite__success")
        route = mock_api.get("/documentgroup/dg-001/groupinvite/inv-001").respond(200, json=fixture)

        # ACT
        result = client.get_field_invite(
            token=token,
            document_group_id="dg-001",
            invite_id="inv-001",
        )

        # ASSERT — response parsed
        assert isinstance(result, GetFieldInviteResponse)
        assert result.invite.id == fixture["invite"]["id"]
        assert result.invite.status == fixture["invite"]["status"]
        assert len(result.invite.steps) == 1
        assert result.invite.steps[0].id == fixture["invite"]["steps"][0]["id"]

        # ASSERT — request built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.url.path == "/documentgroup/dg-001/groupinvite/inv-001"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["accept"] == "application/json"

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """GET /documentgroup/{id}/groupinvite/{inv_id} → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__invite_not_found")
        mock_api.get("/documentgroup/dg-999/groupinvite/inv-999").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            client.get_field_invite(
                token=token,
                document_group_id="dg-999",
                invite_id="inv-999",
            )
