"""Unit tests for document module."""

from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signnow_client.models.folders_lite import FolderLite, GetFoldersResponseLite
from sn_mcp_server.tools.document import (
    _entity_folder_id,
    _get_document,
    _get_document_v3,
    _get_full_document,
    _resolve_folder_name,
    _update_document_fields,
    _upload_document,
)
from sn_mcp_server.tools.models import (
    DocumentGroup,
    DocumentGroupDocument,
    FieldToUpdate,
    UpdateDocumentFields,
    UpdateDocumentFieldsResponse,
    UploadDocumentResponse,
)
from sn_mcp_server.tools.models_v3 import DocumentGroupV3


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
    parent_id: str | None = None,
) -> MagicMock:
    """Build a minimal DocumentResponse mock."""
    doc = MagicMock()
    doc.id = doc_id
    doc.document_name = name
    doc.parent_id = parent_id

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
            make_template=False,
        )

    def test_upload_response_includes_next_steps(self, mock_client: MagicMock) -> None:
        """Successful upload surfaces the three primary next_steps and agent_guidance."""
        mock_client.upload_document.return_value = MagicMock(id="doc_next")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"pdf", filename="contract.pdf")

        assert result.document_id == "doc_next"
        assert len(result.next_steps) == 3
        tools_called = [step.tool for step in result.next_steps]
        assert tools_called == ["create_embedded_sending", "send_invite", "send_invite"]
        # Every step must carry a non-empty intent and description; document_id is on the response.
        for step in result.next_steps:
            assert step.intent
            assert step.description
        # Step 2 (freeform) must instruct the agent to collect a recipient email before calling send_invite.
        assert "email" in result.next_steps[1].description.lower()
        # Step 3 (self-sign) must mention the self_sign flag so the agent picks the right send_invite shape.
        assert "self_sign" in result.next_steps[2].description
        assert result.agent_guidance
        assert "next_steps" in result.agent_guidance

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
            make_template=False,
        )

    def test_upload_url_custom_filename(self, mock_client: MagicMock) -> None:
        """Custom filename overrides URL-derived filename and is transmitted as the document name."""
        mock_client.create_document_from_url.return_value = MagicMock(id="doc_url")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/f?id=1", filename="invoice.pdf")

        assert result.filename == "invoice.pdf"
        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.name == "invoice.pdf"

    def test_upload_url_custom_filename_no_extension_allowed(self, mock_client: MagicMock) -> None:
        """A caller-supplied URL filename without an extension is allowed (SignNow types the fetched file).

        The name is only a display name for URL uploads, so it need not carry an extension —
        matching the lenient handling of URL-path-inferred names.
        """
        mock_client.create_document_from_url.return_value = MagicMock(id="doc_noext")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/f?id=1", filename="My Invoice")

        assert result.filename == "My Invoice"
        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.name == "My Invoice"

    def test_upload_url_inferred_filename_not_transmitted(self, mock_client: MagicMock) -> None:
        """A URL-path-inferred filename is NOT sent as name — SignNow's own naming stays authoritative."""
        mock_client.create_document_from_url.return_value = MagicMock(id="doc_url")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/contract.pdf")

        assert result.filename == "contract.pdf"
        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.name is None

    def test_upload_url_make_template_omitted_for_document(self, mock_client: MagicMock) -> None:
        """Document URL uploads must leave make_template unset (None) so it is excluded from the body.

        The API reads the flag with PHP's !empty(); a transmitted "false" could be treated as
        truthy and silently create a template. Only template uploads set it (see TestUploadTemplate).
        """
        mock_client.create_document_from_url.return_value = MagicMock(id="doc_url")

        _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/contract.pdf")

        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.make_template is None

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
        with pytest.raises(ValueError, match="Provide one of: resource_bytes, file_path, or file_url"):
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


class TestUploadDocumentMakeTemplate:
    """Test cases for _upload_document with make_template=True (upload as a reusable template)."""

    @pytest.fixture(autouse=True)
    def _allow_tmp_path(self, tmp_path: pathlib.Path) -> None:  # type: ignore[misc]
        """Patch SAFE_UPLOAD_BASE to tmp_path so file-based tests pass containment."""
        with patch("sn_mcp_server.tools.document.SAFE_UPLOAD_BASE", tmp_path):
            yield  # type: ignore[misc]

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_upload_from_resource_passes_make_template(self, mock_client: MagicMock) -> None:
        """Resource bytes branch forwards make_template=True to the client."""
        mock_client.upload_document.return_value = MagicMock(id="tpl_res")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"pdf content", filename="contract.pdf", make_template=True)

        assert isinstance(result, UploadDocumentResponse)
        assert result.document_id == "tpl_res"
        assert result.filename == "contract.pdf"
        assert result.source == "resource"
        mock_client.upload_document.assert_called_once_with(
            token=FAKE_TOKEN,
            file_content=b"pdf content",
            filename="contract.pdf",
            check_fields=True,
            make_template=True,
        )

    def test_upload_from_local_path_passes_make_template(self, mock_client: MagicMock, tmp_path: pathlib.Path) -> None:
        """Local file path branch forwards make_template=True to the client."""
        pdf_file = tmp_path / "blueprint.pdf"
        pdf_file.write_bytes(b"pdf bytes")
        mock_client.upload_document.return_value = MagicMock(id="tpl_123")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_path=str(pdf_file), make_template=True)

        assert result.document_id == "tpl_123"
        assert result.filename == "blueprint.pdf"
        assert result.source == "local_file"
        assert mock_client.upload_document.call_args.kwargs["make_template"] is True

    def test_upload_from_url_carries_make_template(self, mock_client: MagicMock) -> None:
        """URL branch delegates to create_document_from_url with make_template=True."""
        mock_client.create_document_from_url.return_value = MagicMock(id="tpl_url")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/nda.pdf", make_template=True)

        assert result.document_id == "tpl_url"
        assert result.filename == "nda.pdf"
        assert result.source == "url"
        mock_client.upload_document.assert_not_called()
        # The URL request must carry make_template=True so SignNow stores a template, not a document.
        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.make_template is True
        # Inferred name is NOT transmitted — SignNow's own naming stays authoritative.
        assert request.name is None

    def test_upload_from_url_custom_filename_transmitted(self, mock_client: MagicMock) -> None:
        """An explicit filename is transmitted as the template name for URL uploads."""
        mock_client.create_document_from_url.return_value = MagicMock(id="tpl_url_named")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/f?id=1", filename="NDA Template.pdf", make_template=True)

        assert result.filename == "NDA Template.pdf"
        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.name == "NDA Template.pdf"

    def test_upload_from_url_custom_filename_no_extension_allowed(self, mock_client: MagicMock) -> None:
        """A caller-supplied URL template name without an extension is allowed (regression for SN-33253).

        SignNow fetches the file and types it server-side for URL uploads, so an extension-less
        display name (e.g. one an agent generates) must not raise 'Cannot determine file type'.
        """
        mock_client.create_document_from_url.return_value = MagicMock(id="tpl_noext")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, file_url="https://example.com/f?id=1", filename="New uploaded template by MCP", make_template=True)

        assert result.filename == "New uploaded template by MCP"
        mock_client.upload_document.assert_not_called()
        request = mock_client.create_document_from_url.call_args.kwargs["request_data"]
        assert request.name == "New uploaded template by MCP"
        assert request.make_template is True

    def test_response_includes_template_next_steps(self, mock_client: MagicMock) -> None:
        """A template upload surfaces template-specific next_steps and agent_guidance."""
        mock_client.upload_document.return_value = MagicMock(id="tpl_next")

        result = _upload_document(client=mock_client, token=FAKE_TOKEN, resource_bytes=b"pdf", filename="contract.pdf", make_template=True)

        tools_called = [step.tool for step in result.next_steps]
        assert tools_called == ["create_from_template", "create_embedded_editor"]
        for step in result.next_steps:
            assert step.intent
            assert step.description
        assert result.agent_guidance
        assert "next_steps" in result.agent_guidance


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


def _folder_tree() -> GetFoldersResponseLite:
    """Full nested hierarchy as get_folder_tree returns it (subfolders nested recursively)."""
    return GetFoldersResponseLite(
        id="root_folder_id",
        name="Root Folder",
        user_id="user123",
        folders=[
            FolderLite(
                id="folder1",
                name="Folder 1",
                user_id="user123",
                sub_folders=[
                    FolderLite(
                        id="nested1",
                        name="Nested One",
                        user_id="user123",
                        sub_folders=[FolderLite(id="deep1", name="Deep One", user_id="user123")],
                    ),
                ],
            ),
            FolderLite(id="folder2", name="Folder 2", user_id="user123"),
            FolderLite(
                id="team_templates",
                name="Team Templates",
                user_id="user123",
                sub_folders=[FolderLite(id="team_nested", name="Team Nested", user_id="user123")],
            ),
        ],
    )


def _doc(doc_id: str = "d1") -> DocumentGroupDocument:
    """Minimal folder-free DocumentGroupDocument (frozen v2 member shape)."""
    return DocumentGroupDocument(id=doc_id, name=f"Doc {doc_id}", roles=[])


def _grp(documents: list[DocumentGroupDocument]) -> DocumentGroup:
    """Wrap documents in a folder-free DocumentGroup (frozen v2 shape)."""
    return DocumentGroup(
        last_updated=0,
        entity_id="grp",
        group_name="G",
        entity_type="document_group",
        invite=None,
        documents=documents,
    )


class TestGetDocumentV2Frozen:
    """Guards that the frozen v2 base does zero folder work after the revert."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_get_document_signature_has_no_folder_flag(self) -> None:
        """_get_document must not expose a resolve_folder_names parameter (guards the revert)."""
        import inspect

        params = inspect.signature(_get_document).parameters
        assert "resolve_folder_names" not in params

    def test_v2_single_document_no_folder_calls(self, mock_client: MagicMock) -> None:
        """A single-document fetch makes no folder-tree call and no is_custom_folder request."""
        mock_client.get_document.return_value = _make_document_response(doc_id="docid", parent_id="deep1")

        result = _get_document(mock_client, "tok", "docid", "document")

        mock_client.get_folder_tree.assert_not_called()
        mock_client.get_document.assert_called_once_with("tok", "docid")
        assert not hasattr(result, "folder_id")
        assert not hasattr(result, "folder_name")

    def test_v2_document_group_has_no_folder_fields(self, mock_client: MagicMock) -> None:
        """A document group fetch is folder-free: no tree call, members fetched without is_custom_folder."""
        from signnow_client.models.document_groups import (
            DocumentGroupV2Data,
            DocumentGroupV2Document,
            GetDocumentGroupV2Response,
        )

        data = DocumentGroupV2Data.model_construct(
            id="dg",
            name="DG",
            folder_id="folder2",
            created=0,
            state="pending",
            invite_id=None,
            pending_step_id=None,
            last_invite_id=None,
            documents=[DocumentGroupV2Document.model_construct(id="m1", field_invites=[])],
            freeform_invite=None,
        )
        mock_client.get_document_group_v2.return_value = GetDocumentGroupV2Response.model_construct(data=data)
        mock_client.get_document.return_value = _make_document_response(doc_id="m1", parent_id="deep1")

        result = _get_document(mock_client, "tok", "dg", "document_group")

        mock_client.get_folder_tree.assert_not_called()
        mock_client.get_document.assert_called_once_with("tok", "m1")
        assert not hasattr(result, "folder_id")
        assert not any(hasattr(doc, "folder_id") for doc in result.documents)

    def test_v2_auto_detect_single_document_folder_free(self, mock_client: MagicMock) -> None:
        """Auto-detect (entity_type=None) resolves a document without any folder work."""
        mock_client.get_document.return_value = _make_document_response(doc_id="docid", parent_id="deep1")

        result = _get_document(mock_client, "tok", "docid", None)

        mock_client.get_document.assert_called_once_with("tok", "docid")
        mock_client.get_folder_tree.assert_not_called()
        assert result.entity_type == "document"

    def test_v2_auto_detect_document_group_folder_free(self, mock_client: MagicMock) -> None:
        """Auto-detect falls back to the document-group probe without is_custom_folder."""
        from signnow_client.exceptions import SignNowAPINotFoundError
        from signnow_client.models.document_groups import (
            DocumentGroupV2Data,
            DocumentGroupV2Document,
            GetDocumentGroupV2Response,
        )

        def _get_document_side_effect(token: str, doc_id: str, **kwargs: Any) -> Any:
            if doc_id == "dg":
                raise SignNowAPINotFoundError("not a document")
            return _make_document_response(doc_id=doc_id, parent_id="deep1")

        mock_client.get_document.side_effect = _get_document_side_effect
        data = DocumentGroupV2Data.model_construct(
            id="dg",
            name="DG",
            folder_id="folder2",
            created=0,
            state="pending",
            invite_id=None,
            pending_step_id=None,
            last_invite_id=None,
            documents=[DocumentGroupV2Document.model_construct(id="m1", field_invites=[])],
            freeform_invite=None,
        )
        mock_client.get_document_group_v2.return_value = GetDocumentGroupV2Response.model_construct(data=data)

        result = _get_document(mock_client, "tok", "dg", None)

        mock_client.get_folder_tree.assert_not_called()
        assert result.entity_type == "document_group"
        assert mock_client.get_document.call_args_list[-1] == (("tok", "m1"), {})

    def test_v2_template_group_folder_free(self, mock_client: MagicMock) -> None:
        """A template group base fetch pulls members without is_custom_folder and sets no folder."""
        tg = MagicMock()
        tg.id = "tg"
        tg.group_name = "TG"
        tg.folder_id = "folder1"
        member = MagicMock()
        member.id = "t1"
        tg.templates = [member]
        mock_client.get_document_group_template.return_value = tg
        mock_client.get_document.return_value = _make_document_response(doc_id="t1", parent_id="deep1")

        result = _get_document(mock_client, "tok", "tg", "template_group")

        mock_client.get_folder_tree.assert_not_called()
        mock_client.get_document.assert_called_once_with("tok", "t1")
        assert result.entity_type == "template_group"
        assert not hasattr(result, "folder_id")

    def test_v2_tool_delegates_without_folder_flag(self) -> None:
        """The v2 get_document tool resolves the token then calls _get_document with no folder flag."""
        tool = _capture_get_document_tools()["2.0"]
        ctx = AsyncMock()
        client = MagicMock()
        expected = DocumentGroup(last_updated=0, entity_id="grp", group_name="G", entity_type="document", invite=None, documents=[])

        with (
            patch("sn_mcp_server.tools.signnow._get_token_and_client", return_value=("tok", client)),
            patch("sn_mcp_server.tools.signnow._get_document", return_value=expected) as mock_get,
        ):
            result = tool(ctx, "grp", "document")

        assert result == expected
        mock_get.assert_called_once_with(client, "tok", "grp", "document")


class TestResolveFolderName:
    """Tests for the v3 _resolve_folder_name helper."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_none_skips_tree_call(self, mock_client: MagicMock) -> None:
        """folder_id=None returns None and makes no get_folder_tree call."""
        assert _resolve_folder_name(mock_client, "tok", None) is None
        mock_client.get_folder_tree.assert_not_called()

    def test_resolves_deeply_nested(self, mock_client: MagicMock) -> None:
        """A subfolder several levels deep resolves from the single nested tree call."""
        mock_client.get_folder_tree.return_value = _folder_tree()

        assert _resolve_folder_name(mock_client, "tok", "deep1") == "Deep One"
        mock_client.get_folder_tree.assert_called_once_with("tok")

    def test_resolves_root_and_team(self, mock_client: MagicMock) -> None:
        """Root folder and team-folder subfolders resolve from the tree."""
        mock_client.get_folder_tree.return_value = _folder_tree()

        assert _resolve_folder_name(mock_client, "tok", "root_folder_id") == "Root Folder"
        assert _resolve_folder_name(mock_client, "tok", "team_nested") == "Team Nested"

    def test_absent_returns_none(self, mock_client: MagicMock) -> None:
        """A folder absent from the tree returns None (caller keeps the raw folder_id)."""
        mock_client.get_folder_tree.return_value = _folder_tree()

        assert _resolve_folder_name(mock_client, "tok", "ghost") is None


class TestEntityFolderId:
    """Tests for the v3 _entity_folder_id helper (dispatch on resolved entity_type)."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_single_document(self, mock_client: MagicMock) -> None:
        """'document' re-reads via get_document(is_custom_folder=True) and returns parent_id."""
        mock_client.get_document.return_value = _make_document_response(doc_id="doc", parent_id="deep1")

        assert _entity_folder_id(mock_client, "tok", "doc", "document") == "deep1"
        mock_client.get_document.assert_called_once_with("tok", "doc", is_custom_folder=True)

    def test_document_group(self, mock_client: MagicMock) -> None:
        """'document_group' returns the group's data.folder_id."""
        mock_client.get_document_group_v2.return_value.data.folder_id = "folder2"

        assert _entity_folder_id(mock_client, "tok", "dg", "document_group") == "folder2"
        mock_client.get_document_group_v2.assert_called_once_with("tok", "dg")

    def test_template_group(self, mock_client: MagicMock) -> None:
        """'template_group' returns the template group's folder_id."""
        mock_client.get_document_group_template.return_value.folder_id = "folder1"

        assert _entity_folder_id(mock_client, "tok", "tg", "template_group") == "folder1"
        mock_client.get_document_group_template.assert_called_once_with("tok", "tg")


def _v3_base_group(entity_type: str, entity_id: str = "e1", documents: list[DocumentGroupDocument] | None = None) -> DocumentGroup:
    """A folder-free base DocumentGroup as the shared base returns it."""
    return DocumentGroup(
        last_updated=7,
        entity_id=entity_id,
        group_name="Entity",
        entity_type=entity_type,
        invite=None,
        documents=documents if documents is not None else [_doc("m1")],
    )


class TestGetDocumentV3:
    """Tests for _get_document_v3 (frozen base + entity-level folder info)."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_single_document_resolves_entity_folder(self, mock_client: MagicMock) -> None:
        """A single document resolves entity folder_id/name; members carry no folder fields."""
        mock_client.get_document.return_value = _make_document_response(doc_id="docid", parent_id="deep1")
        mock_client.get_folder_tree.return_value = _folder_tree()

        with patch("sn_mcp_server.tools.document._get_document", return_value=_v3_base_group("document", "docid", [_doc("docid")])):
            result = _get_document_v3(mock_client, "tok", "docid", None)

        assert isinstance(result, DocumentGroupV3)
        assert result.folder_id == "deep1"
        assert result.folder_name == "Deep One"
        assert not hasattr(result.documents[0], "folder_id")

    def test_document_group_entity_level_only(self, mock_client: MagicMock) -> None:
        """A document group resolves folder at entity level only; members are not re-fetched."""
        mock_client.get_document_group_v2.return_value.data.folder_id = "folder2"
        mock_client.get_folder_tree.return_value = _folder_tree()

        with patch("sn_mcp_server.tools.document._get_document", return_value=_v3_base_group("document_group", "dg", [_doc("m1"), _doc("m2")])):
            result = _get_document_v3(mock_client, "tok", "dg", "document_group")

        assert result.folder_id == "folder2"
        assert result.folder_name == "Folder 2"
        assert all(isinstance(doc, DocumentGroupDocument) for doc in result.documents)
        mock_client.get_document.assert_not_called()

    def test_template_group_entity_level(self, mock_client: MagicMock) -> None:
        """A template group resolves folder at entity level."""
        mock_client.get_document_group_template.return_value.folder_id = "folder1"
        mock_client.get_folder_tree.return_value = _folder_tree()

        with patch("sn_mcp_server.tools.document._get_document", return_value=_v3_base_group("template_group", "tg")):
            result = _get_document_v3(mock_client, "tok", "tg", "template_group")

        assert result.folder_id == "folder1"
        assert result.folder_name == "Folder 1"
        assert result.entity_type == "template_group"

    def test_no_folder_skips_tree(self, mock_client: MagicMock) -> None:
        """parent_id=None yields null folder fields and skips the tree call."""
        mock_client.get_document.return_value = _make_document_response(doc_id="docid", parent_id=None)

        with patch("sn_mcp_server.tools.document._get_document", return_value=_v3_base_group("document", "docid", [_doc("docid")])):
            result = _get_document_v3(mock_client, "tok", "docid", "document")

        assert result.folder_id is None
        assert result.folder_name is None
        mock_client.get_folder_tree.assert_not_called()

    def test_folder_absent_keeps_id_null_name(self, mock_client: MagicMock) -> None:
        """A folder_id absent from the tree keeps the id but leaves folder_name None."""
        mock_client.get_document.return_value = _make_document_response(doc_id="docid", parent_id="ghost")
        mock_client.get_folder_tree.return_value = _folder_tree()

        with patch("sn_mcp_server.tools.document._get_document", return_value=_v3_base_group("document", "docid", [_doc("docid")])):
            result = _get_document_v3(mock_client, "tok", "docid", "document")

        assert result.folder_id == "ghost"
        assert result.folder_name is None

    def test_entity_not_found_raises(self, mock_client: MagicMock) -> None:
        """A not-found ValueError from the base propagates and no folder calls are made."""
        with patch(
            "sn_mcp_server.tools.document._get_document",
            side_effect=ValueError("Entity with ID missing not found as either document, template, template group or document group"),
        ):
            with pytest.raises(ValueError, match="not found as either document"):
                _get_document_v3(mock_client, "tok", "missing", None)

        mock_client.get_folder_tree.assert_not_called()
        mock_client.get_document.assert_not_called()
        mock_client.get_document_group_v2.assert_not_called()
        mock_client.get_document_group_template.assert_not_called()


def _capture_get_document_tools() -> dict[str, Any]:
    """Register all tool versions and return {version: fn} for the get_document tool."""
    from fastmcp import FastMCP

    from sn_mcp_server.tools import register_tools

    mcp: Any = FastMCP("test-get-document-versions")
    captured: dict[str, Any] = {}
    original_tool = mcp.tool

    def recording_tool(*args: Any, **kwargs: Any) -> Any:
        decorator = original_tool(*args, **kwargs)
        name: str = kwargs.get("name", "")
        version: str = kwargs.get("version", "")

        def wrap(fn: Any) -> Any:
            if name == "get_document":
                captured[version] = fn
            return decorator(fn)

        return wrap

    mcp.tool = recording_tool

    class _StubCfg:
        pass

    register_tools(mcp, _StubCfg())  # type: ignore[arg-type]
    return captured


def _return_annotation_name(fn: Any) -> str:
    """Return the name of a function's return annotation (handles string annotations)."""
    ann = fn.__annotations__["return"]
    return ann if isinstance(ann, str) else ann.__name__


class TestGetDocumentV3Tool:
    """Tests for the get_document@3.0 MCP tool wrapper and per-version return types."""

    def test_tool_delegates_to_get_document_v3(self) -> None:
        """The v3 tool resolves the token then calls _get_document_v3 and returns its result."""
        tool = _capture_get_document_tools()["3.0"]
        ctx = AsyncMock()
        client = MagicMock()
        expected = DocumentGroupV3(last_updated=0, entity_id="grp", group_name="G", entity_type="document", documents=[])

        with (
            patch("sn_mcp_server.tools.signnow_v3._get_token_and_client", return_value=("tok", client)),
            patch("sn_mcp_server.tools.signnow_v3._get_document_v3", return_value=expected) as mock_v3,
        ):
            result = tool(ctx, "grp", "document")

        assert result == expected
        mock_v3.assert_called_once_with(client, "tok", "grp", "document")

    def test_return_types_per_version(self) -> None:
        """v1 → DocumentGroupV1, v2 → DocumentGroup, v3 → DocumentGroupV3."""
        tools = _capture_get_document_tools()
        assert _return_annotation_name(tools["1.0"]) == "DocumentGroupV1"
        assert _return_annotation_name(tools["2.0"]) == "DocumentGroup"
        assert _return_annotation_name(tools["3.0"]) == "DocumentGroupV3"
