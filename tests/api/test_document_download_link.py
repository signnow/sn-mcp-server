"""API-level tests for SignNowAPIClient.get_document_download_link."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models import DocumentDownloadLinkResponse


class TestGetDocumentDownloadLink:
    """Verify client.get_document_download_link builds the right request and parses responses."""

    def test_success_returns_parsed_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /document/{id}/download/link → 200 → DocumentDownloadLinkResponse."""
        # ARRANGE
        fixture = load_fixture("post_download_link__success")
        route = mock_api.post("/document/doc_001/download/link").respond(200, json=fixture)

        # ACT
        result = client.get_document_download_link(token=token, document_id="doc_001")

        # ASSERT — response parsed into correct model
        assert isinstance(result, DocumentDownloadLinkResponse)
        assert result.link == fixture["link"]

        # ASSERT — request was built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/document/doc_001/download/link"
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"

    def test_not_found_raises(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /document/{id}/download/link → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        route = mock_api.post("/document/doc_999/download/link").respond(
            404,
            json=error_fixture,
        )

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError) as exc_info:
            client.get_document_download_link(token=token, document_id="doc_999")

        # ASSERT — HTTP call was made
        assert route.called

        assert exc_info.value.status_code == 404
        assert exc_info.value.message == "Document not found"
        assert exc_info.value.response_data == error_fixture
