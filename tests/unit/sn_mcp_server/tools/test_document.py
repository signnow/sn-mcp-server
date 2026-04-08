"""Unit tests for document module."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

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


FAKE_TOKEN = "tok"  # noqa: S105


class TestUploadDocument:
    """Test cases for _upload_document."""

    @pytest.fixture(autouse=True)
    def _allow_tmp_path(self, tmp_path: pathlib.Path) -> None:  # type: ignore[misc]
        """Patch SAFE_UPLOAD_BASE to tmp_path so file-based tests pass containment."""
        with patch("sn_mcp_server.tools.document.SAFE_UPLOAD_BASE", tmp_path):
            yield  # type: ignore[misc]

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_upload_from_resource_happy(self, mock_client: MagicMock) -> None:
        """Resource bytes branch returns correct UploadDocumentResponse."""
        mock_client.upload_document.return_value = MagicMock(id="doc_res")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"pdf content", filename="contract.pdf")

        assert isinstance(result, UploadDocumentResponse)
        assert result.document_id == "doc_res"
        assert result.filename == "contract.pdf"
        assert result.source == "resource"
        mock_client.upload_document.assert_called_once_with(
            token=FAKE_TOKEN,
            file_content=b"pdf content",
            filename="contract.pdf",
            check_fields=True,
        )

    def test_upload_from_local_path_happy(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Local file path branch returns correct UploadDocumentResponse."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"pdf bytes")
        mock_client.upload_document.return_value = MagicMock(id="doc_123")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(pdf_file))

        assert result.document_id == "doc_123"
        assert result.filename == "test.pdf"
        assert result.source == "local_file"

    def test_upload_from_url_happy(self, mock_client: MagicMock) -> None:
        """URL branch returns correct UploadDocumentResponse."""
        mock_client.create_document_from_url.return_value = MagicMock(id="doc_456")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/contract.pdf")

        assert result.document_id == "doc_456"
        assert result.filename == "contract.pdf"
        assert result.source == "url"

    def test_upload_custom_filename(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Custom filename overrides the derived filename."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"pdf bytes")
        mock_client.upload_document.return_value = MagicMock(id="doc_789")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(pdf_file), filename="My Contract.pdf")

        assert result.filename == "My Contract.pdf"
        mock_client.upload_document.assert_called_once_with(
            token=FAKE_TOKEN,
            file_content=b"pdf bytes",
            filename="My Contract.pdf",
            check_fields=True,
        )

    def test_upload_url_custom_filename(self, mock_client: MagicMock) -> None:
        """Custom filename overrides URL-derived filename."""
        mock_client.create_document_from_url.return_value = MagicMock(id="doc_url")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/f?id=1", filename="invoice.pdf")

        assert result.filename == "invoice.pdf"

    def test_resource_bytes_no_filename_raises(self, mock_client: MagicMock) -> None:
        """resource_bytes without filename raises ValueError."""
        with pytest.raises(ValueError, match="filename is required when uploading from a resource URI"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"pdf")

    def test_multiple_sources_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Providing two sources raises ValueError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"bytes")
        with pytest.raises(ValueError, match="Provide exactly one of"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(pdf_file), file_url="https://example.com/f.pdf")

    def test_no_source_raises(self, mock_client: MagicMock) -> None:
        """Providing no source raises ValueError."""
        with pytest.raises(ValueError, match="Provide one of: resource_uri, file_path, or file_url"):
            _upload_document(client=mock_client, token=FAKE_TOKEN)

    def test_file_not_found_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Non-existent local path raises ValueError."""
        nonexistent = tmp_path / "definitely_does_not_exist_xyzabc.pdf"
        with pytest.raises(ValueError, match="File not found"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(nonexistent))

    def test_unsupported_extension_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Unsupported file extension raises ValueError."""
        exe_file = tmp_path / "test.exe"
        exe_file.write_bytes(b"data")
        with pytest.raises(ValueError, match="Unsupported file type '.exe'"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(exe_file))

    def test_file_too_large_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """File exceeding 40 MB raises ValueError after reading content."""
        huge = tmp_path / "huge.pdf"
        # L-3: Write just 1 byte — mock read_bytes to return oversized content
        huge.write_bytes(b"x")
        oversized = b"x" * (40 * 1024 * 1024 + 1)
        with patch.object(pathlib.Path, "read_bytes", return_value=oversized):
            with pytest.raises(ValueError, match="File too large"):
                _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(huge))
        mock_client.upload_document.assert_not_called()

    def test_url_invalid_scheme_raises(self, mock_client: MagicMock) -> None:
        """URL with non-http/https scheme raises ValueError."""
        with pytest.raises(ValueError, match="URL must use http or https"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="ftp://example.com/f.pdf")

    def test_tilde_expansion(self, mock_client: MagicMock) -> None:
        """~ in file_path is expanded to an absolute path in the error message."""
        # Use real home for this test since ~ expansion goes to the actual home directory
        with patch("sn_mcp_server.tools.document.SAFE_UPLOAD_BASE", pathlib.Path.home().resolve()):
            with pytest.raises(ValueError, match="File not found") as exc_info:
                _upload_document(client=mock_client, token=FAKE_TOKEN, file_path="~/nonexistent_test_file_xyzabc.pdf")
            assert "~" not in str(exc_info.value)

    def test_url_filename_extraction(self, mock_client: MagicMock) -> None:
        """Filename is extracted from the URL path."""
        mock_client.create_document_from_url.return_value = MagicMock(id="x")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://cdn.example.com/files/report.docx")

        assert result.filename == "report.docx"

    def test_url_no_extension_allowed(self, mock_client: MagicMock) -> None:
        """URL without a detectable extension is allowed (SignNow validates server-side)."""
        mock_client.create_document_from_url.return_value = MagicMock(id="y")

        # URL with a path segment but no extension: filename is extracted as "12345"
        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://api.example.com/download/12345")

        assert result.source == "url"
        # Filename inferred from URL path; no extension → allowed (server validates)
        assert result.filename == "12345"

    def test_url_no_path_segment_filename_is_none(self, mock_client: MagicMock) -> None:
        """URL with no path segment yields filename=None in the response."""
        mock_client.create_document_from_url.return_value = MagicMock(id="z")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://cdn.example.com")

        assert result.source == "url"
        assert result.filename is None

    def test_url_unsupported_extension_raises(self, mock_client: MagicMock) -> None:
        """URL pointing to an unsupported file type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported file type '.exe'"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/file.exe")

    def test_path_is_not_a_file_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Directory path (not a file) raises ValueError."""
        with pytest.raises(ValueError, match="Path is not a file"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(tmp_path))

    def test_resource_bytes_unsupported_extension_raises(self, mock_client: MagicMock) -> None:
        """resource_bytes with an unsupported filename extension raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported file type '.exe'"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"data", filename="payload.exe")

    def test_resource_bytes_too_large_raises(self, mock_client: MagicMock) -> None:
        """resource_bytes exceeding MAX_FILE_SIZE_BYTES raises ValueError before upload."""
        # L-3: Create a small bytes object and mock len() check via direct size
        oversized = b"x" * (40 * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match="File too large"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=oversized, filename="big.pdf")
        mock_client.upload_document.assert_not_called()

    def test_path_outside_home_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """file_path resolving outside the allowed base raises ValueError (C-1/C-2)."""
        # Override the autouse fixture with a specific base that excludes /etc
        with patch("sn_mcp_server.tools.document.SAFE_UPLOAD_BASE", tmp_path):
            with pytest.raises(ValueError, match="file_path must be within the home directory"):
                _upload_document(client=mock_client, token=FAKE_TOKEN, file_path="/etc/hosts")

    def test_symlink_outside_home_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Symlink resolving outside allowed base raises ValueError (C-2)."""
        # Create a symlink in tmp_path that points outside
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        link = subdir / "trick.pdf"
        link.symlink_to("/etc/hosts")
        # Set base to subdir — resolved path of symlink is /etc/hosts which is outside
        with patch("sn_mcp_server.tools.document.SAFE_UPLOAD_BASE", subdir):
            with pytest.raises(ValueError, match="file_path must be within the home directory"):
                _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(link))

    def test_url_empty_netloc_raises(self, mock_client: MagicMock) -> None:
        """URL without hostname raises ValueError (M-2)."""
        with pytest.raises(ValueError, match="URL must include a hostname"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https:///path/file.pdf")

    def test_resource_bytes_no_extension_raises(self, mock_client: MagicMock) -> None:
        """resource_bytes with extensionless filename raises clear error (M-1)."""
        with pytest.raises(ValueError, match="Cannot determine file type for 'contract'"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"data", filename="contract")

    def test_local_path_no_extension_raises(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Local file with no extension raises clear error (M-1)."""
        no_ext = tmp_path / "contract"
        no_ext.write_bytes(b"data")
        with pytest.raises(ValueError, match="Cannot determine file type for 'contract'"):
            _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(no_ext))


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
