"""
Integration tests for create_template — full stack from tool logic → SignNowAPIClient → HTTP.

HTTP layer is mocked via respx; no real network calls.
Tests validate the full flow: business logic → SignNowAPIClient → request construction → response parsing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.create_template import create_template
from sn_mcp_server.tools.models import CreateTemplateResult

DOC_ID = "doc_integration_1"
GRP_ID = "grp_integration_1"


class TestCreateTemplateDocumentPath:
    """Integration tests for create_template with entity_type='document'."""

    async def test_document_happy_path(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /template → 200 → CreateTemplateResult with template_id populated."""
        mock_api.post("/template").respond(200, json={"id": "tmpl_abc123"})

        result = create_template(sn_client, token, DOC_ID, "My NDA", "document")

        assert isinstance(result, CreateTemplateResult)
        assert result.template_id == "tmpl_abc123"
        assert result.template_name == "My NDA"
        assert result.entity_type == "document"

    async def test_document_not_found_raises(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /template → 404 → ValueError raised."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post("/template").respond(404, json=error_fixture)

        with pytest.raises((ValueError, SignNowAPINotFoundError)):
            create_template(sn_client, token, "bad_doc_id", "NDA", "document")


class TestCreateTemplateDocumentGroupPath:
    """Integration tests for create_template with entity_type='document_group'."""

    async def test_document_group_happy_path(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /v2/document-groups/{id}/document-group-template → 202 → template_id=None."""
        mock_api.post(f"/v2/document-groups/{GRP_ID}/document-group-template").respond(202, json={"message": "ok"})

        result = create_template(sn_client, token, GRP_ID, "NDA Group", "document_group")

        assert isinstance(result, CreateTemplateResult)
        assert result.template_id is None
        assert result.template_name == "NDA Group"
        assert result.entity_type == "document_group"

    async def test_document_group_not_found_raises(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /v2/document-groups/{id}/document-group-template → 404 → ValueError."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post("/v2/document-groups/bad_grp/document-group-template").respond(404, json=error_fixture)

        with pytest.raises(ValueError, match="Document group not found: bad_grp"):
            create_template(sn_client, token, "bad_grp", "NDA Group", "document_group")


class TestCreateTemplateAutoDetect:
    """Integration tests for create_template with entity_type=None (auto-detection)."""

    async def test_auto_detect_resolves_document_group(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None + group GET succeeds → entity_type='document_group' in result."""
        group_fixture = load_fixture("get_document_group_v2__with_pending_invite")
        mock_api.get(f"/v2/document-groups/{GRP_ID}").respond(200, json=group_fixture)
        mock_api.post(f"/v2/document-groups/{GRP_ID}/document-group-template").respond(202, json={"message": "ok"})

        result = create_template(sn_client, token, GRP_ID, "NDA Group")

        assert result.entity_type == "document_group"
        assert result.template_id is None

    async def test_auto_detect_falls_back_to_document(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None + group GET 404 + document GET 200 → entity_type='document'."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get(f"/v2/document-groups/{DOC_ID}").respond(404, json=error_fixture)
        mock_api.get(f"/document/{DOC_ID}").respond(200, json=load_fixture("get_document__with_pending_invite"))
        mock_api.post("/template").respond(200, json={"id": "tmpl_fallback"})

        result = create_template(sn_client, token, DOC_ID, "My NDA")

        assert result.entity_type == "document"
        assert result.template_id == "tmpl_fallback"

    async def test_auto_detect_both_not_found_raises(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None + both GETs return 404 → ValueError."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get("/v2/document-groups/missing_id").respond(404, json=error_fixture)
        mock_api.get("/document/missing_id").respond(404, json=error_fixture)

        with pytest.raises(ValueError, match="not found as document or document_group"):
            create_template(sn_client, token, "missing_id", "NDA")
