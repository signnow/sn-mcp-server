"""
Integration tests for _get_document_v3 — business logic wired to a real SignNowAPIClient.

HTTP layer is mocked via respx; no real network calls.
Tests validate the full flow: _get_document_v3 → SignNowAPIClient → HTTP construction →
response parsing, including the entity-level folder info added in the v3.0 contract.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from sn_mcp_server.tools.document import _get_document_v3
from sn_mcp_server.tools.models_v3 import DocumentGroupV3

DOC_ID = "docid"

_FOLDER_TREE: dict[str, Any] = {
    "id": "root_folder_id",
    "name": "Root Folder",
    "user_id": "user123",
    "folders": [
        {"id": "folder1", "name": "Folder 1", "user_id": "user123"},
        {"id": "folder2", "name": "Folder 2", "user_id": "user123"},
    ],
}


class TestGetDocumentV3ReturnsFolder:
    """Integration tests for the v3.0 folder-enriched get_document flow."""

    def test_get_document_v3_returns_folder(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """A single document resolves its entity-level folder_id and folder_name."""
        # ARRANGE — document lives in folder1 (surfaced via is_custom_folder re-read)
        doc_fixture = load_fixture("get_document__no_field_invites")
        doc_fixture["parent_id"] = "folder1"

        mock_api.get(f"/document/{DOC_ID}").respond(200, json=doc_fixture)
        folder_route = mock_api.get("/v1/folder").respond(200, json=_FOLDER_TREE)

        # ACT
        result = _get_document_v3(client=sn_client, token=token, entity_id=DOC_ID, entity_type="document")

        # ASSERT
        assert isinstance(result, DocumentGroupV3)
        assert result.entity_type == "document"
        assert result.folder_id == "folder1"
        assert result.folder_name == "Folder 1"
        assert folder_route.called

    def test_get_document_v3_entity_not_found_raises(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None with all probes 404 → ValueError with the entity_id in the message."""
        # ARRANGE — every auto-detect probe returns not-found
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get("/document/missing").respond(404, json=error_fixture)
        mock_api.get("/v2/document-groups/missing").respond(404, json=error_fixture)
        mock_api.get("/documentgroup/template/missing").respond(404, json=error_fixture)
        folder_route = mock_api.get("/v1/folder").respond(200, json=_FOLDER_TREE)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="missing"):
            _get_document_v3(client=sn_client, token=token, entity_id="missing", entity_type=None)

        # No folder resolution is attempted when the base fetch fails.
        assert not folder_route.called
