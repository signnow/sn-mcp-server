"""Integration tests for _get_document_download_link tool."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.document_download_link import _get_document_download_link
from sn_mcp_server.tools.models import DocumentDownloadLinkResponse


class TestGetDocumentDownloadLink:
    """Integration tests for _get_document_download_link."""

    def test_single_document_returns_download_link(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Single document → POST /document/{id}/download/link → download link returned."""
        # ARRANGE
        fixture = load_fixture("post_download_link__success")
        route = mock_api.post("/document/doc_001/download/link").respond(200, json=fixture)

        # ACT
        result = _get_document_download_link(
            entity_id="doc_001",
            entity_type="document",
            token=token,
            client=sn_client,
        )

        # ASSERT — HTTP call was made
        assert route.called

        # ASSERT — result matches fixture
        assert isinstance(result, DocumentDownloadLinkResponse)
        assert result.link == fixture["link"]

    def test_single_document_not_found_raises(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Document not found → API returns 404 → SignNowAPINotFoundError raised."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        route = mock_api.post("/document/doc_999/download/link").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError) as exc_info:
            _get_document_download_link(
                entity_id="doc_999",
                entity_type="document",
                token=token,
                client=sn_client,
            )

        # ASSERT — HTTP call was made
        assert route.called

        assert exc_info.value.status_code == 404
        assert exc_info.value.message == "Document not found"
        assert exc_info.value.response_data == error_fixture
