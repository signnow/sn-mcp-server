"""
Integration tests for _view_document — tool function wired to real SignNowAPIClient.

HTTP layer is mocked via respx; no real network calls.
Tests validate the full flow: tool function → SignNowAPIClient → HTTP construction → response parsing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.document_view import _view_document
from sn_mcp_server.tools.models import ViewDocumentResponse

DOC_ID = "doc1"
GRP_ID = "grp1"


class TestViewDocumentGroupExplicit:
    """Integration tests for _view_document with entity_type='document_group'."""

    def test_happy_path_returns_view_response(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Document group → name fetched, embedded view created, ViewDocumentResponse returned."""
        # ARRANGE
        group_fixture = load_fixture("get_document_group_v2__with_pending_invite")
        view_fixture = load_fixture("post_embedded_view_group__success")

        mock_api.get(f"/v2/document-groups/{GRP_ID}").respond(200, json=group_fixture)
        mock_api.post(f"/v2/document-groups/{GRP_ID}/embedded-view").respond(200, json=view_fixture)

        # ACT
        result = _view_document(
            client=sn_client,
            token=token,
            entity_id=GRP_ID,
            entity_type="document_group",
            link_expiration_minutes=None,
        )

        # ASSERT
        assert isinstance(result, ViewDocumentResponse)
        assert result.entity_id == GRP_ID
        assert result.entity_type == "document_group"
        assert result.document_name == group_fixture["data"]["name"]
        assert result.view_link == view_fixture["data"]["link"]

    def test_not_found_propagates_error(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """404 on GET document group → SignNowAPINotFoundError propagates to caller."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get(f"/v2/document-groups/{GRP_ID}").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            _view_document(
                client=sn_client,
                token=token,
                entity_id=GRP_ID,
                entity_type="document_group",
                link_expiration_minutes=None,
            )


class TestViewDocumentExplicit:
    """Integration tests for _view_document with entity_type='document'."""

    def test_happy_path_returns_view_response(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Document → name fetched, embedded view created, ViewDocumentResponse returned."""
        # ARRANGE
        doc_fixture = load_fixture("get_document__with_pending_invite")
        view_fixture = load_fixture("post_embedded_view__success")

        mock_api.get(f"/document/{DOC_ID}").respond(200, json=doc_fixture)
        mock_api.post(f"/v2/documents/{DOC_ID}/embedded-view").respond(200, json=view_fixture)

        # ACT
        result = _view_document(
            client=sn_client,
            token=token,
            entity_id=DOC_ID,
            entity_type="document",
            link_expiration_minutes=None,
        )

        # ASSERT
        assert isinstance(result, ViewDocumentResponse)
        assert result.entity_id == DOC_ID
        assert result.entity_type == "document"
        assert result.document_name == doc_fixture["document_name"]
        assert result.view_link == view_fixture["data"]["link"]

    def test_not_found_propagates_error(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """404 on GET document → SignNowAPINotFoundError propagates to caller."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get("/document/doc-missing").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(SignNowAPINotFoundError):
            _view_document(
                client=sn_client,
                token=token,
                entity_id="doc-missing",
                entity_type="document",
                link_expiration_minutes=None,
            )


class TestViewDocumentAutoDetect:
    """Integration tests for _view_document with entity_type=None (auto-detection)."""

    def test_auto_detects_document_group_first(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → tries document_group first → succeeds → document not called."""
        # ARRANGE
        group_fixture = load_fixture("get_document_group_v2__with_pending_invite")
        view_fixture = load_fixture("post_embedded_view_group__success")

        group_route = mock_api.get(f"/v2/document-groups/{GRP_ID}").respond(200, json=group_fixture)
        mock_api.post(f"/v2/document-groups/{GRP_ID}/embedded-view").respond(200, json=view_fixture)

        # ACT
        result = _view_document(
            client=sn_client,
            token=token,
            entity_id=GRP_ID,
            entity_type=None,
            link_expiration_minutes=None,
        )

        # ASSERT — resolved as document_group
        assert isinstance(result, ViewDocumentResponse)
        assert result.entity_type == "document_group"
        assert result.document_name == group_fixture["data"]["name"]
        assert result.view_link == view_fixture["data"]["link"]
        assert group_route.called

    def test_auto_detect_falls_back_to_document(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → group 404 → falls back to document → succeeds."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        doc_fixture = load_fixture("get_document__with_pending_invite")
        view_fixture = load_fixture("post_embedded_view__success")

        mock_api.get(f"/v2/document-groups/{DOC_ID}").respond(404, json=error_fixture)
        mock_api.get(f"/document/{DOC_ID}").respond(200, json=doc_fixture)
        mock_api.post(f"/v2/documents/{DOC_ID}/embedded-view").respond(200, json=view_fixture)

        # ACT
        result = _view_document(
            client=sn_client,
            token=token,
            entity_id=DOC_ID,
            entity_type=None,
            link_expiration_minutes=None,
        )

        # ASSERT — resolved as document
        assert isinstance(result, ViewDocumentResponse)
        assert result.entity_type == "document"
        assert result.document_name == doc_fixture["document_name"]
        assert result.view_link == view_fixture["data"]["link"]

    def test_auto_detect_raises_when_both_not_found(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → both 404 → ValueError with entity_id in message."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get("/v2/document-groups/unknown-id").respond(404, json=error_fixture)
        mock_api.get("/document/unknown-id").respond(404, json=error_fixture)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="unknown-id"):
            _view_document(
                client=sn_client,
                token=token,
                entity_id="unknown-id",
                entity_type=None,
                link_expiration_minutes=None,
            )
