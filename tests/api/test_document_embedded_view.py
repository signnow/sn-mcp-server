"""API-level tests for document and document group embedded view client methods."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models import (
    CreateDocumentEmbeddedViewRequest,
    CreateDocumentEmbeddedViewResponse,
    CreateDocumentGroupEmbeddedViewRequest,
    CreateDocumentGroupEmbeddedViewResponse,
)


class TestCreateDocumentEmbeddedView:
    """Verify client.create_document_embedded_view builds the right request and parses responses."""

    def test_success_returns_parsed_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /v2/documents/{id}/embedded-view → 200 → CreateDocumentEmbeddedViewResponse."""
        # ARRANGE
        fixture = load_fixture("post_embedded_view__success")
        route = mock_api.post("/v2/documents/doc_001/embedded-view").respond(200, json=fixture)
        request_data = CreateDocumentEmbeddedViewRequest()

        # ACT
        result = client.create_document_embedded_view(
            token=token,
            document_id="doc_001",
            request_data=request_data,
        )

        # ASSERT — response parsed into correct model
        assert isinstance(result, CreateDocumentEmbeddedViewResponse)
        assert result.data.link == fixture["data"]["link"]

        # ASSERT — request was built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/v2/documents/doc_001/embedded-view"
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
        """POST /v2/documents/{id}/embedded-view → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        route = mock_api.post("/v2/documents/doc_999/embedded-view").respond(
            404,
            json=error_fixture,
        )
        request_data = CreateDocumentEmbeddedViewRequest()

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError) as exc_info:
            client.create_document_embedded_view(
                token=token,
                document_id="doc_999",
                request_data=request_data,
            )

        assert route.called
        assert exc_info.value.status_code == 404
        assert exc_info.value.response_data == error_fixture


class TestCreateDocumentGroupEmbeddedView:
    """Verify client.create_document_group_embedded_view builds the right request and parses responses."""

    def test_success_returns_parsed_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /v2/document-groups/{id}/embedded-view → 200 → CreateDocumentGroupEmbeddedViewResponse."""
        # ARRANGE
        fixture = load_fixture("post_embedded_view_group__success")
        route = mock_api.post("/v2/document-groups/grp_001/embedded-view").respond(200, json=fixture)
        request_data = CreateDocumentGroupEmbeddedViewRequest()

        # ACT
        result = client.create_document_group_embedded_view(
            token=token,
            document_group_id="grp_001",
            request_data=request_data,
        )

        # ASSERT — response parsed into correct model
        assert isinstance(result, CreateDocumentGroupEmbeddedViewResponse)
        assert result.data.link == fixture["data"]["link"]

        # ASSERT — request was built correctly
        assert route.called
        request = route.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/v2/document-groups/grp_001/embedded-view"
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
        """POST /v2/document-groups/{id}/embedded-view → 404 → SignNowAPINotFoundError."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        route = mock_api.post("/v2/document-groups/grp_999/embedded-view").respond(
            404,
            json=error_fixture,
        )
        request_data = CreateDocumentGroupEmbeddedViewRequest()

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError) as exc_info:
            client.create_document_group_embedded_view(
                token=token,
                document_group_id="grp_999",
                request_data=request_data,
            )

        assert route.called
        assert exc_info.value.status_code == 404
        assert exc_info.value.response_data == error_fixture
