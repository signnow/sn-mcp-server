"""Unit tests for document module."""

from unittest.mock import MagicMock

import pytest

from sn_mcp_server.tools.document import (
    _get_full_document,
    _update_document_fields,
    _upload_document,
)
from sn_mcp_server.tools.models import (
    FieldToUpdate,
    UpdateDocumentFields,
    UpdateDocumentFieldsResponse,
    UploadDocumentResponse,
)


def _make_document_field(
    field_id: str = "f1",
    field_type: str = "text",
    role: str = "Signer",
    prefilled_text: str = "Hello",
    name: str = "my_field",
) -> MagicMock:
    """Build a minimal DocumentField mock."""
    field = MagicMock()
    field.id = field_id
    field.type = field_type
    field.role = role
    field.json_attributes = MagicMock()
    field.json_attributes.prefilled_text = prefilled_text
    field.json_attributes.name = name
    return field


def _make_document_response(
    doc_id: str = "doc1",
    name: str = "Test Doc",
    roles: list | None = None,
    fields: list | None = None,
    field_invites: list | None = None,
) -> MagicMock:
    """Build a minimal DocumentResponse mock."""
    doc = MagicMock()
    doc.id = doc_id
    doc.document_name = name

    role_objs = []
    for r in roles or ["Signer"]:
        role_mock = MagicMock()
        role_mock.name = r
        role_objs.append(role_mock)
    doc.roles = role_objs

    doc.fields = fields if fields is not None else []
    doc.field_invites = field_invites if field_invites is not None else []
    return doc


class TestUploadDocument:
    """Test cases for _upload_document."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_returns_upload_response_with_correct_fields(self, mock_client: MagicMock) -> None:
        """Test successful upload returns UploadDocumentResponse with document_id and filename."""
        mock_client.upload_document.return_value = MagicMock(id="uploaded_doc_123")

        result = _upload_document(b"file content", "contract.pdf", True, "tok", mock_client)

        assert isinstance(result, UploadDocumentResponse)
        assert result.document_id == "uploaded_doc_123"
        assert result.filename == "contract.pdf"
        assert result.check_fields is True

    def test_passes_check_fields_false(self, mock_client: MagicMock) -> None:
        """Test check_fields=False is propagated correctly."""
        mock_client.upload_document.return_value = MagicMock(id="doc_no_check")

        result = _upload_document(b"data", "plain.pdf", False, "tok", mock_client)

        assert result.check_fields is False
        mock_client.upload_document.assert_called_once_with(
            token="tok",  # noqa: S106
            file_content=b"data",
            filename="plain.pdf",
            check_fields=False,
        )


class TestGetFullDocument:
    """Test cases for _get_full_document field extraction."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_returns_document_group_document_with_text_fields(self, mock_client: MagicMock) -> None:
        """Test only text-type fields are included in the result."""
        text_field = _make_document_field("f1", "text", "Signer", "filled value", "field_name")
        sig_field = _make_document_field("f2", "signature", "Signer", "", "sig_field")
        doc = _make_document_response("doc1", "My Doc", ["Signer"], [text_field, sig_field])

        result = _get_full_document(mock_client, "tok", "doc1", doc)

        assert result.id == "doc1"
        assert result.name == "My Doc"
        assert result.roles == ["Signer"]
        assert len(result.fields) == 1
        assert result.fields[0].id == "f1"
        assert result.fields[0].type == "text"
        assert result.fields[0].value == "filled value"
        assert result.fields[0].name == "field_name"

    def test_returns_empty_fields_when_no_text_fields(self, mock_client: MagicMock) -> None:
        """Test empty fields list when document has no text-type fields."""
        checkbox_field = _make_document_field("f3", "checkbox", "Approver", "", "chk")
        doc = _make_document_response("doc2", "Empty Fields Doc", ["Approver"], [checkbox_field])

        result = _get_full_document(mock_client, "tok", "doc2", doc)

        assert result.fields == []

    def test_field_role_id_set_from_role_attribute(self, mock_client: MagicMock) -> None:
        """Test role_id in DocumentField is set from field.role (not field.role_id)."""
        text_field = _make_document_field("f10", "text", "Reviewer", "val", "reviewer_field")
        doc = _make_document_response("doc3", "Role Doc", ["Reviewer"], [text_field])

        result = _get_full_document(mock_client, "tok", "doc3", doc)

        assert result.fields[0].role_id == "Reviewer"

    def test_prefilled_text_none_becomes_empty_string(self, mock_client: MagicMock) -> None:
        """Test None prefilled_text is stored as empty string."""
        text_field = _make_document_field("f5", "text", "Signer", None, "empty_prefill")
        doc = _make_document_response("doc4", "Doc", ["Signer"], [text_field])

        result = _get_full_document(mock_client, "tok", "doc4", doc)

        assert result.fields[0].value == ""

    def test_multiple_roles_all_present(self, mock_client: MagicMock) -> None:
        """Test that all document roles appear in the result."""
        doc = _make_document_response("doc5", "Multi Role", ["Signer", "Reviewer", "Approver"], [])

        result = _get_full_document(mock_client, "tok", "doc5", doc)

        assert result.roles == ["Signer", "Reviewer", "Approver"]


class TestUpdateDocumentFields:
    """Test cases for _update_document_fields."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_returns_success_result_when_prefill_succeeds(self, mock_client: MagicMock) -> None:
        """Test successful update produces updated=True result."""
        mock_client.prefill_text_fields.return_value = True
        request = UpdateDocumentFields(
            document_id="doc123",
            fields=[FieldToUpdate(name="field1", value="new value")],
        )

        result = _update_document_fields(mock_client, "tok", [request])

        assert isinstance(result, UpdateDocumentFieldsResponse)
        assert len(result.results) == 1
        assert result.results[0].document_id == "doc123"
        assert result.results[0].updated is True
        assert result.results[0].reason is None

    def test_returns_failure_result_when_prefill_raises(self, mock_client: MagicMock) -> None:
        """Test exception during prefill is caught and stored as reason."""
        mock_client.prefill_text_fields.side_effect = ValueError("field not found for doc_fail")
        request = UpdateDocumentFields(
            document_id="doc_fail",
            fields=[FieldToUpdate(name="bad_field", value="value")],
        )

        result = _update_document_fields(mock_client, "tok", [request])

        assert result.results[0].updated is False
        assert "field not found for doc_fail" in result.results[0].reason

    def test_processes_multiple_documents_independently(self, mock_client: MagicMock) -> None:
        """Test each document update is independent and failures don't stop others."""
        mock_client.prefill_text_fields.side_effect = [True, Exception("server error")]
        requests = [
            UpdateDocumentFields(document_id="doc_ok", fields=[FieldToUpdate(name="f", value="v")]),
            UpdateDocumentFields(document_id="doc_fail", fields=[FieldToUpdate(name="f2", value="v2")]),
        ]

        result = _update_document_fields(mock_client, "tok", requests)

        assert len(result.results) == 2
        assert result.results[0].updated is True
        assert result.results[1].updated is False

    def test_empty_update_list_returns_empty_results(self, mock_client: MagicMock) -> None:
        """Test empty update request list returns response with no results."""
        result = _update_document_fields(mock_client, "tok", [])

        assert result.results == []
        mock_client.prefill_text_fields.assert_not_called()
