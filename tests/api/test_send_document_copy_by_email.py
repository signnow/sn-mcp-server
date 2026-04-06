"""API-level tests for SignNowAPIClient.send_document_copy_by_email."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.templates_and_documents import SendDocumentCopyByEmailResponse


class TestSendDocumentCopyByEmail:
    """Verify client.send_document_copy_by_email builds the correct HTTP request and parses responses."""

    def test_success_with_subject_and_message(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /document/{id}/email2 with all fields → 200 → SendDocumentCopyByEmailResponse."""
        # ARRANGE
        fixture = load_fixture("post_email2__success")
        route = mock_api.post("/document/doc_001/email2").respond(200, json=fixture)

        # ACT
        result = client.send_document_copy_by_email(
            token=token,
            document_id="doc_001",
            emails=["signer@example.com"],
            message="Please sign this document.",
            subject="Reminder: Your signature is needed",
        )

        # ASSERT — response parsed correctly
        assert isinstance(result, SendDocumentCopyByEmailResponse)
        assert result.status == "success"

        # ASSERT — request built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/document/doc_001/email2"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"

        body = json.loads(request.content)
        assert body["emails"] == ["signer@example.com"]
        assert body["message"] == "Please sign this document."
        assert body["subject"] == "Reminder: Your signature is needed"

    def test_success_without_optional_fields_excluded_from_body(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Null message and subject are excluded from the JSON body (model_dump drops None)."""
        # ARRANGE
        fixture = load_fixture("post_email2__success")
        route = mock_api.post("/document/doc_001/email2").respond(200, json=fixture)

        # ACT
        client.send_document_copy_by_email(
            token=token,
            document_id="doc_001",
            emails=["signer@example.com"],
        )

        # ASSERT — optional keys absent from body
        assert route.called
        body = json.loads(route.calls.last.request.content)
        assert "message" not in body
        assert "subject" not in body
        assert body["emails"] == ["signer@example.com"]

    def test_empty_emails_raises_value_error_before_http(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """Empty emails list → ValueError raised before any HTTP call is made."""
        # ARRANGE
        route = mock_api.post("/document/doc_001/email2").respond(200, json={"status": "success"})

        # ACT & ASSERT
        with pytest.raises(ValueError, match="at least one"):
            client.send_document_copy_by_email(token=token, document_id="doc_001", emails=[])

        assert not route.called

    def test_too_many_emails_raises_value_error_before_http(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """More than 5 emails → ValueError raised before any HTTP call is made."""
        # ARRANGE
        route = mock_api.post("/document/doc_001/email2").respond(200, json={"status": "success"})
        six_emails = [f"user{i}@example.com" for i in range(6)]

        # ACT & ASSERT
        with pytest.raises(ValueError, match="5"):
            client.send_document_copy_by_email(token=token, document_id="doc_001", emails=six_emails)

        assert not route.called

    def test_api_error_raises_signnow_api_error(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Non-2xx response → SignNowAPIError raised with correct status code."""
        # ARRANGE
        fixture = load_fixture("error__email2_unverified_sender")
        route = mock_api.post("/document/doc_001/email2").respond(
            422,
            json=fixture,
        )

        # ACT & ASSERT
        with pytest.raises(SignNowAPIError) as exc_info:
            client.send_document_copy_by_email(
                token=token,
                document_id="doc_001",
                emails=["signer@example.com"],
            )

        assert route.called
        assert exc_info.value.status_code == 422
