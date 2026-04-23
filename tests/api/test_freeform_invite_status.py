"""API-level tests for list_document_freeform_invites and list_document_group_documents."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIHTTPError
from signnow_client.models import ListDocumentFreeformInvitesResponse, ListDocumentGroupDocumentsResponse


class TestListDocumentFreeformInvites:
    """GET /v2/documents/{document_id}/free-form-invites"""

    def test_url_method_and_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        payload = {
            "data": [
                {
                    "id": "inv_ff_1",
                    "status": "pending",
                    "created": 1578561895,
                    "email": "signer1@email.com",
                }
            ],
            "meta": {
                "pagination": {
                    "total": 1,
                    "count": 1,
                    "per_page": 15,
                    "current_page": 1,
                    "total_pages": 1,
                    "links": [],
                }
            },
        }
        route = mock_api.get("/v2/documents/doc_abc/free-form-invites").respond(200, json=payload)

        result = client.list_document_freeform_invites(token, "doc_abc")

        assert isinstance(result, ListDocumentFreeformInvitesResponse)
        assert result.data[0].id == "inv_ff_1"
        assert result.data[0].email == "signer1@email.com"
        assert route.called
        req = route.calls.last.request
        assert req.method == "GET"
        parsed = urlparse(str(req.url))
        assert parsed.path == "/v2/documents/doc_abc/free-form-invites"
        q = parse_qs(parsed.query)
        assert q.get("per_page") == ["15"]
        assert q.get("page") == ["1"]

    def test_http_400_raises(self, client: SignNowAPIClient, mock_api: respx.MockRouter, token: str) -> None:
        mock_api.get("/v2/documents/missing/free-form-invites").respond(400, json={"errors": [{"message": "Document not found"}]})

        with pytest.raises(SignNowAPIHTTPError) as exc_info:
            client.list_document_freeform_invites(token, "missing")

        assert exc_info.value.status_code == 400


class TestListDocumentGroupDocuments:
    """GET /v2/document-groups/{document_group_id}/documents"""

    def test_url_method_and_model(
        self,
        client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        payload = {
            "data": [
                {
                    "id": "cd19b02135214e6e9ec0a5f40b430e3b6f58873f",
                    "signature_requests": [
                        {
                            "user_id": "7946ea48e09b4c0e9db529dbe6e7157248b15afa",
                            "status": "pending",
                            "email": "a@ex.com",
                        }
                    ],
                }
            ],
            "meta": {"pagination": {"total": 1, "count": 1, "per_page": 15, "current_page": 1, "total_pages": 1, "links": []}},
        }
        route = mock_api.get("/v2/document-groups/grp1/documents").respond(200, json=payload)

        result = client.list_document_group_documents(token, "grp1")

        assert isinstance(result, ListDocumentGroupDocumentsResponse)
        assert result.data[0].id == "cd19b02135214e6e9ec0a5f40b430e3b6f58873f"
        assert result.data[0].signature_requests[0].email == "a@ex.com"
        assert route.called
        req = route.calls.last.request
        assert req.method == "GET"
        parsed = urlparse(str(req.url))
        assert parsed.path == "/v2/document-groups/grp1/documents"
        q = parse_qs(parsed.query)
        assert q.get("per_page") == ["15"]
        assert q.get("page") == ["1"]

    def test_http_404_raises(self, client: SignNowAPIClient, mock_api: respx.MockRouter, token: str) -> None:
        mock_api.get("/v2/document-groups/ghost/documents").respond(
            404,
            json={"errors": [{"code": 19002010, "message": "Document group 'ghost' not found."}]},
        )

        with pytest.raises(SignNowAPIHTTPError) as exc_info:
            client.list_document_group_documents(token, "ghost")

        assert exc_info.value.status_code == 404
