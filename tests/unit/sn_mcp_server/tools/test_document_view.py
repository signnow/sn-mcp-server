"""Unit tests for document_view.py — _view_document business logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIError
from signnow_client.models.document_groups import (
    CreateDocumentGroupEmbeddedViewResponse,
    DocumentGroupV2Data,
    EmbeddedViewData,
    GetDocumentGroupV2Response,
)
from signnow_client.models.templates_and_documents import (
    CreateDocumentEmbeddedViewResponse,
    DocumentResponse,
)
from sn_mcp_server.tools.document_view import _view_document
from sn_mcp_server.tools.models import ViewDocumentResponse

TOKEN = "unit-test-token"  # noqa: S105
DOC_ID = "doc-abc"
GRP_ID = "grp-xyz"
VIEW_LINK = "https://app.signnow.com/webapp/document/doc-abc?access_token=tok&embedded=1"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _group_resp(name: str = "My Group") -> GetDocumentGroupV2Response:
    """Minimal GetDocumentGroupV2Response — only data.name is accessed by _view_document."""
    data = DocumentGroupV2Data.model_construct(name=name, documents=[])
    return GetDocumentGroupV2Response.model_construct(data=data)


def _doc_resp(name: str = "My Doc") -> DocumentResponse:
    """Minimal DocumentResponse — only document_name is accessed."""
    return DocumentResponse.model_construct(document_name=name)


def _group_view_resp(link: str = VIEW_LINK) -> CreateDocumentGroupEmbeddedViewResponse:
    """CreateDocumentGroupEmbeddedViewResponse with a link."""
    return CreateDocumentGroupEmbeddedViewResponse(data=EmbeddedViewData(link=link))


def _doc_view_resp(link: str = VIEW_LINK) -> CreateDocumentEmbeddedViewResponse:
    """CreateDocumentEmbeddedViewResponse with a link."""
    return CreateDocumentEmbeddedViewResponse(data=CreateDocumentEmbeddedViewResponse.Data(link=link))


# ---------------------------------------------------------------------------
# Tests: explicit entity_type='document_group'
# ---------------------------------------------------------------------------


class TestViewDocumentGroupExplicit:
    """Tests for _view_document(entity_type='document_group')."""

    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        """Client with a document_group found and embedded view created."""
        client = MagicMock()
        client.get_document_group_v2.return_value = _group_resp("Sales Proposal")
        client.create_document_group_embedded_view.return_value = _group_view_resp()
        return client

    def test_returns_view_document_response(self, mock_client: MagicMock) -> None:
        """Explicit document_group → result is ViewDocumentResponse."""
        result = _view_document(GRP_ID, "document_group", None, TOKEN, mock_client)
        assert isinstance(result, ViewDocumentResponse)

    def test_view_link_extracted(self, mock_client: MagicMock) -> None:
        """view_link matches embedded view response data.link."""
        result = _view_document(GRP_ID, "document_group", None, TOKEN, mock_client)
        assert result.view_link == VIEW_LINK

    def test_entity_id_and_type_set(self, mock_client: MagicMock) -> None:
        """entity_id and entity_type set correctly."""
        result = _view_document(GRP_ID, "document_group", None, TOKEN, mock_client)
        assert result.entity_id == GRP_ID
        assert result.entity_type == "document_group"

    def test_document_name_fetched_from_group(self, mock_client: MagicMock) -> None:
        """document_name comes from get_document_group_v2 data.name."""
        result = _view_document(GRP_ID, "document_group", None, TOKEN, mock_client)
        assert result.document_name == "Sales Proposal"

    def test_link_expiration_forwarded(self, mock_client: MagicMock) -> None:
        """link_expiration_minutes forwarded to CreateDocumentGroupEmbeddedViewRequest."""
        _view_document(GRP_ID, "document_group", 86400, TOKEN, mock_client)

        args = mock_client.create_document_group_embedded_view.call_args[0]
        request = args[2]
        assert request.link_expiration == 86400

    def test_group_id_passed_to_embedded_view(self, mock_client: MagicMock) -> None:
        """document_group_id passed correctly to create_document_group_embedded_view."""
        _view_document(GRP_ID, "document_group", None, TOKEN, mock_client)

        args = mock_client.create_document_group_embedded_view.call_args[0]
        assert args[1] == GRP_ID

    def test_get_document_not_called(self, mock_client: MagicMock) -> None:
        """get_document is never called for entity_type='document_group'."""
        _view_document(GRP_ID, "document_group", None, TOKEN, mock_client)
        mock_client.get_document.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: explicit entity_type='document'
# ---------------------------------------------------------------------------


class TestViewDocumentExplicit:
    """Tests for _view_document(entity_type='document')."""

    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        """Client with a document found and embedded view created."""
        client = MagicMock()
        client.get_document.return_value = _doc_resp("Invoice Q4")
        client.create_document_embedded_view.return_value = _doc_view_resp()
        return client

    def test_returns_view_document_response(self, mock_client: MagicMock) -> None:
        """Explicit document → result is ViewDocumentResponse."""
        result = _view_document(DOC_ID, "document", None, TOKEN, mock_client)
        assert isinstance(result, ViewDocumentResponse)

    def test_view_link_extracted(self, mock_client: MagicMock) -> None:
        """view_link matches embedded view response data.link."""
        result = _view_document(DOC_ID, "document", None, TOKEN, mock_client)
        assert result.view_link == VIEW_LINK

    def test_entity_id_and_type_set(self, mock_client: MagicMock) -> None:
        """entity_id and entity_type set correctly."""
        result = _view_document(DOC_ID, "document", None, TOKEN, mock_client)
        assert result.entity_id == DOC_ID
        assert result.entity_type == "document"

    def test_document_name_fetched_from_doc(self, mock_client: MagicMock) -> None:
        """document_name comes from DocumentResponse.document_name."""
        result = _view_document(DOC_ID, "document", None, TOKEN, mock_client)
        assert result.document_name == "Invoice Q4"

    def test_link_expiration_forwarded(self, mock_client: MagicMock) -> None:
        """link_expiration_minutes forwarded to CreateDocumentEmbeddedViewRequest."""
        _view_document(DOC_ID, "document", 43200, TOKEN, mock_client)

        args = mock_client.create_document_embedded_view.call_args[0]
        request = args[2]
        assert request.link_expiration == 43200

    def test_doc_id_passed_to_embedded_view(self, mock_client: MagicMock) -> None:
        """document_id passed correctly to create_document_embedded_view."""
        _view_document(DOC_ID, "document", None, TOKEN, mock_client)

        args = mock_client.create_document_embedded_view.call_args[0]
        assert args[1] == DOC_ID

    def test_get_document_group_not_called(self, mock_client: MagicMock) -> None:
        """get_document_group_v2 is never called for entity_type='document'."""
        _view_document(DOC_ID, "document", None, TOKEN, mock_client)
        mock_client.get_document_group_v2.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: auto-detect (entity_type=None)
# ---------------------------------------------------------------------------


class TestViewDocumentAutoDetect:
    """Tests for _view_document(entity_type=None) — auto-detection logic."""

    def test_group_detected_first(self) -> None:
        """Auto-detect: group found → entity_type='document_group', name set."""
        client = MagicMock()
        client.get_document_group_v2.return_value = _group_resp("Group A")
        client.create_document_group_embedded_view.return_value = _group_view_resp()

        result = _view_document(GRP_ID, None, None, TOKEN, client)

        assert result.entity_type == "document_group"
        assert result.document_name == "Group A"

    def test_group_found_document_api_not_called(self) -> None:
        """Auto-detect: group found → get_document never called."""
        client = MagicMock()
        client.get_document_group_v2.return_value = _group_resp()
        client.create_document_group_embedded_view.return_value = _group_view_resp()

        _view_document(GRP_ID, None, None, TOKEN, client)

        client.get_document.assert_not_called()

    def test_group_found_name_not_refetched(self) -> None:
        """Auto-detect: name set during detection — get_document_group_v2 called only once."""
        client = MagicMock()
        client.get_document_group_v2.return_value = _group_resp()
        client.create_document_group_embedded_view.return_value = _group_view_resp()

        _view_document(GRP_ID, None, None, TOKEN, client)

        client.get_document_group_v2.assert_called_once()

    def test_fallback_to_document_when_group_raises(self) -> None:
        """Auto-detect: group API raises → falls back to document."""
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIError("Not Found", 404)
        client.get_document.return_value = _doc_resp("Fallback Doc")
        client.create_document_embedded_view.return_value = _doc_view_resp()

        result = _view_document(DOC_ID, None, None, TOKEN, client)

        assert result.entity_type == "document"
        assert result.document_name == "Fallback Doc"

    def test_fallback_document_name_not_refetched(self) -> None:
        """Auto-detect: fallback doc name set during detection — get_document called once."""
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIError("Not Found", 404)
        client.get_document.return_value = _doc_resp()
        client.create_document_embedded_view.return_value = _doc_view_resp()

        _view_document(DOC_ID, None, None, TOKEN, client)

        client.get_document.assert_called_once()

    def test_raises_value_error_when_both_not_found(self) -> None:
        """Auto-detect: both group and document raise → ValueError with entity_id in message."""
        client = MagicMock()
        client.get_document_group_v2.side_effect = SignNowAPIError("Not Found", 404)
        client.get_document.side_effect = SignNowAPIError("Not Found", 404)

        with pytest.raises(ValueError, match="unknown-id"):
            _view_document("unknown-id", None, None, TOKEN, client)

    def test_value_error_message_mentions_not_found(self) -> None:
        """ValueError message contains 'not found' context."""
        client = MagicMock()
        client.get_document_group_v2.side_effect = Exception("timeout")
        client.get_document.side_effect = Exception("timeout")

        with pytest.raises(ValueError, match="not found"):
            _view_document("bad-id", None, None, TOKEN, client)
