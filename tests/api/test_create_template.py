"""
API-level tests for SignNowAPIClient.create_template and create_document_group_template_from_group.

Tests validate HTTP method, URL, headers, and request body construction.
HTTP layer is mocked via respx; no real network calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import CreateDocumentGroupTemplateFromGroupRequest
from signnow_client.models.templates_and_documents import CreateTemplateRequest, CreateTemplateResponse


class TestCreateTemplateAPI:
    """Verify client.create_template builds correct requests and parses responses."""

    def test_post_url_method_and_body(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /template with correct body → 200 → CreateTemplateResponse with id."""
        route = mock_api.post("/template").respond(200, json={"id": "tmpl_new_1"})

        result = client.create_template(
            token=token,
            request_data=CreateTemplateRequest(document_id="doc_src_1", document_name="My NDA"),
        )

        assert route.called
        request = route.calls.last.request

        assert request.method == "POST"
        assert request.url.path == "/template"
        assert request.headers["authorization"] == f"Bearer {token}"

        body = json.loads(request.content)
        assert body["document_id"] == "doc_src_1"
        assert body["document_name"] == "My NDA"

        assert isinstance(result, CreateTemplateResponse)
        assert result.id == "tmpl_new_1"

    def test_404_raises_api_error(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /template → 404 → SignNowAPIError raised with status_code=404."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post("/template").respond(404, json=error_fixture)

        with pytest.raises(SignNowAPIError) as exc_info:
            client.create_template(
                token=token,
                request_data=CreateTemplateRequest(document_id="bad_id", document_name="x"),
            )

        assert exc_info.value.status_code == 404

    def test_403_raises_api_error(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /template → 403 → SignNowAPIError raised with status_code=403."""
        mock_api.post("/template").respond(403, json={"errors": [{"message": "Forbidden"}]})

        with pytest.raises(SignNowAPIError) as exc_info:
            client.create_template(
                token=token,
                request_data=CreateTemplateRequest(document_id="doc1", document_name="x"),
            )

        assert exc_info.value.status_code == 403


class TestCreateDocumentGroupTemplateFromGroupAPI:
    """Verify client.create_document_group_template_from_group builds correct requests."""

    def test_post_url_method_and_body(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /v2/document-groups/{id}/document-group-template with correct body → 202 → True."""
        route = mock_api.post("/v2/document-groups/grp_src_1/document-group-template").respond(202, json={})

        result = client.create_document_group_template_from_group(
            token=token,
            doc_group_id="grp_src_1",
            request_data=CreateDocumentGroupTemplateFromGroupRequest(name="NDA Package"),
        )

        assert route.called
        request = route.calls.last.request

        assert request.method == "POST"
        assert request.url.path == "/v2/document-groups/grp_src_1/document-group-template"
        assert request.headers["authorization"] == f"Bearer {token}"

        body = json.loads(request.content)
        assert body["name"] == "NDA Package"

        assert result is True

    def test_404_raises_api_error(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """POST /v2/document-groups/{id}/document-group-template → 404 → SignNowAPIError."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post("/v2/document-groups/bad_grp/document-group-template").respond(404, json=error_fixture)

        with pytest.raises(SignNowAPIError) as exc_info:
            client.create_document_group_template_from_group(
                token=token,
                doc_group_id="bad_grp",
                request_data=CreateDocumentGroupTemplateFromGroupRequest(name="x"),
            )

        assert exc_info.value.status_code == 404
