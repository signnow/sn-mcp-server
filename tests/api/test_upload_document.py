"""
API-level tests for SignNowAPIClient.upload_document and create_document_from_url.

Tests validate HTTP method, URL, headers, and request body construction.
HTTP layer is mocked via respx; no real network calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIAuthenticationError, SignNowAPINotFoundError, SignNowAPITimeoutError
from signnow_client.models.templates_and_documents import CreateDocumentFromUrlRequest


class TestUploadDocumentAPI:
    """Verify client.upload_document and client.create_document_from_url build correct requests."""

    def test_upload_document_request(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /document with multipart body → 200 → UploadDocumentResponse parsed."""
        # ARRANGE
        fixture = load_fixture("post_upload_document__success")
        route = mock_api.post("/document").respond(200, json=fixture)

        # ACT
        result = client.upload_document(token=token, file_content=b"pdf", filename="a.pdf", check_fields=True)

        # ASSERT — call was made
        assert route.called
        request = route.calls.last.request

        assert request.method == "POST"
        assert request.url.path == "/document"
        assert request.headers["authorization"] == f"Bearer {token}"

        # Assert multipart body contains file part and check_fields
        body = request.content.decode("latin-1")
        assert "a.pdf" in body
        assert "check_fields" in body
        assert "true" in body

        assert result.id == fixture["id"]

    def test_create_from_url_request(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /v2/documents/url with JSON body → 200 → CreateDocumentFromUrlResponse parsed."""
        # ARRANGE
        fixture = load_fixture("post_create_document_from_url__success")
        route = mock_api.post("/v2/documents/url").respond(200, json=fixture)

        # ACT
        result = client.create_document_from_url(
            token=token,
            request_data=CreateDocumentFromUrlRequest(url="https://x.com/f.pdf", check_fields=True),
        )

        # ASSERT — call was made
        assert route.called
        request = route.calls.last.request

        assert request.method == "POST"
        assert request.url.path == "/v2/documents/url"
        assert request.headers["authorization"] == f"Bearer {token}"

        body = json.loads(request.content)
        assert body["url"] == "https://x.com/f.pdf"
        assert body["check_fields"] is True

        assert result.id == fixture["id"]

    def test_upload_document_not_found(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /document → 404 → SignNowAPINotFoundError raised."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post("/document").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError) as exc_info:
            client.upload_document(token=token, file_content=b"pdf", filename="a.pdf", check_fields=True)

        assert exc_info.value.status_code == 404

    def test_upload_document_auth_error(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /document → 401 → SignNowAPIAuthenticationError raised."""
        # ARRANGE
        mock_api.post("/document").respond(401, json={"error": "Unauthorized"})

        # ACT & ASSERT
        with pytest.raises(SignNowAPIAuthenticationError) as exc_info:
            client.upload_document(token=token, file_content=b"pdf", filename="a.pdf", check_fields=True)

        assert exc_info.value.status_code == 401

    def test_create_from_url_timeout(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /v2/documents/url → timeout → SignNowAPITimeoutError raised."""
        # ARRANGE
        mock_api.post("/v2/documents/url").mock(side_effect=httpx.TimeoutException("timeout"))

        # ACT & ASSERT
        with pytest.raises(SignNowAPITimeoutError):
            client.create_document_from_url(
                token=token,
                request_data=CreateDocumentFromUrlRequest(url="https://x.com/f.pdf", check_fields=True),
            )
