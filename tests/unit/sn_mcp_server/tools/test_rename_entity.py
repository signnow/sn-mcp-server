"""Unit tests for rename_entity tool."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIHTTPError
from signnow_client.models.templates_and_documents import DocumentResponse
from sn_mcp_server.tools.models import RenameEntityResponse
from sn_mcp_server.tools.rename_entity import _auto_detect_entity_type, _rename_entity

FAKE_TOKEN = "test-token"  # noqa: S105


class TestAutoDetectEntityType:
    """Tests for _auto_detect_entity_type."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_detects_document_group(self, mock_client: MagicMock) -> None:
        """Returns 'document_group' when get_document_group_v2 succeeds."""
        mock_client.get_document_group_v2.return_value = MagicMock()

        result = _auto_detect_entity_type(mock_client, FAKE_TOKEN, "grp123")

        assert result == "document_group"
        mock_client.get_document_group_v2.assert_called_once_with(FAKE_TOKEN, "grp123")
        mock_client.get_document.assert_not_called()

    def test_detects_template_when_document_group_404(self, mock_client: MagicMock) -> None:
        """Falls back to get_document and returns 'template' when document.template is True."""
        not_found = SignNowAPIHTTPError("Not found", 404)
        mock_client.get_document_group_v2.side_effect = not_found
        mock_client.get_document.return_value = MagicMock(spec=DocumentResponse, template=True)

        result = _auto_detect_entity_type(mock_client, FAKE_TOKEN, "tpl123")

        assert result == "template"

    def test_detects_document_when_template_flag_false(self, mock_client: MagicMock) -> None:
        """Returns 'document' when document.template is False."""
        not_found = SignNowAPIHTTPError("Not found", 404)
        mock_client.get_document_group_v2.side_effect = not_found
        mock_client.get_document.return_value = MagicMock(spec=DocumentResponse, template=False)

        result = _auto_detect_entity_type(mock_client, FAKE_TOKEN, "doc123")

        assert result == "document"

    def test_raises_when_both_lookups_fail(self, mock_client: MagicMock) -> None:
        """Raises ValueError when entity is not found as any type."""
        not_found = SignNowAPIHTTPError("Not found", 404)
        mock_client.get_document_group_v2.side_effect = not_found
        mock_client.get_document.side_effect = not_found

        with pytest.raises(ValueError, match="not found"):
            _auto_detect_entity_type(mock_client, FAKE_TOKEN, "unknown_id")

    def test_reraises_non_404_from_document_group(self, mock_client: MagicMock) -> None:
        """Re-raises non-404 HTTP errors from document group lookup."""
        server_error = SignNowAPIHTTPError("Server error", 500)
        mock_client.get_document_group_v2.side_effect = server_error

        with pytest.raises(SignNowAPIHTTPError):
            _auto_detect_entity_type(mock_client, FAKE_TOKEN, "entity_id")

    def test_reraises_non_404_from_document(self, mock_client: MagicMock) -> None:
        """Re-raises non-404 HTTP errors from document lookup."""
        not_found = SignNowAPIHTTPError("Not found", 404)
        server_error = SignNowAPIHTTPError("Forbidden", 403)
        mock_client.get_document_group_v2.side_effect = not_found
        mock_client.get_document.side_effect = server_error

        with pytest.raises(SignNowAPIHTTPError):
            _auto_detect_entity_type(mock_client, FAKE_TOKEN, "entity_id")


class TestRenameEntity:
    """Tests for _rename_entity dispatcher."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_rename_document_group_explicit_type(self, mock_client: MagicMock) -> None:
        """Calls rename_document_group when entity_type='document_group'."""
        result = _rename_entity("grp1", "New Group Name", "document_group", FAKE_TOKEN, mock_client)

        mock_client.rename_document_group.assert_called_once_with(FAKE_TOKEN, "grp1", "New Group Name")
        assert isinstance(result, RenameEntityResponse)
        assert result.entity_id == "grp1"
        assert result.entity_type == "document_group"
        assert result.new_name == "New Group Name"

    def test_rename_template_group_explicit_type(self, mock_client: MagicMock) -> None:
        """Calls rename_template_group when entity_type='template_group'."""
        result = _rename_entity("dgt1", "New DGT Name", "template_group", FAKE_TOKEN, mock_client)

        mock_client.rename_template_group.assert_called_once_with(FAKE_TOKEN, "dgt1", "New DGT Name")
        assert result.entity_type == "template_group"
        assert result.new_name == "New DGT Name"

    def test_rename_document_explicit_type(self, mock_client: MagicMock) -> None:
        """Calls rename_document when entity_type='document'."""
        result = _rename_entity("doc1", "New Doc Name", "document", FAKE_TOKEN, mock_client)

        mock_client.rename_document.assert_called_once_with(FAKE_TOKEN, "doc1", "New Doc Name")
        assert result.entity_type == "document"

    def test_rename_template_explicit_type(self, mock_client: MagicMock) -> None:
        """Calls rename_document (same endpoint) when entity_type='template'."""
        result = _rename_entity("tpl1", "New Template Name", "template", FAKE_TOKEN, mock_client)

        mock_client.rename_document.assert_called_once_with(FAKE_TOKEN, "tpl1", "New Template Name")
        assert result.entity_type == "template"

    def test_auto_detect_document_group(self, mock_client: MagicMock) -> None:
        """Auto-detects document_group when entity_type is None."""
        mock_client.get_document_group_v2.return_value = MagicMock()

        result = _rename_entity("grp1", "New Name", None, FAKE_TOKEN, mock_client)

        mock_client.rename_document_group.assert_called_once()
        assert result.entity_type == "document_group"

    def test_auto_detect_template(self, mock_client: MagicMock) -> None:
        """Auto-detects template when document.template=True."""
        mock_client.get_document_group_v2.side_effect = SignNowAPIHTTPError("Not found", 404)
        mock_client.get_document.return_value = MagicMock(spec=DocumentResponse, template=True)

        result = _rename_entity("tpl1", "New Name", None, FAKE_TOKEN, mock_client)

        mock_client.rename_document.assert_called_once_with(FAKE_TOKEN, "tpl1", "New Name")
        assert result.entity_type == "template"

    def test_auto_detect_document(self, mock_client: MagicMock) -> None:
        """Auto-detects document when document.template=False."""
        mock_client.get_document_group_v2.side_effect = SignNowAPIHTTPError("Not found", 404)
        mock_client.get_document.return_value = MagicMock(spec=DocumentResponse, template=False)

        result = _rename_entity("doc1", "New Name", None, FAKE_TOKEN, mock_client)

        mock_client.rename_document.assert_called_once_with(FAKE_TOKEN, "doc1", "New Name")
        assert result.entity_type == "document"

    def test_invalid_entity_type_raises(self, mock_client: MagicMock) -> None:
        """Raises ValueError for unsupported entity_type."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            _rename_entity("id1", "New Name", "folder", FAKE_TOKEN, mock_client)  # type: ignore[arg-type]

    def test_template_group_cannot_be_auto_detected(self, mock_client: MagicMock) -> None:
        """Auto-detect falls back to ValueError when entity can't be found — template_group must be explicit."""
        mock_client.get_document_group_v2.side_effect = SignNowAPIHTTPError("Not found", 404)
        mock_client.get_document.side_effect = SignNowAPIHTTPError("Not found", 404)

        with pytest.raises(ValueError, match="template_group"):
            _rename_entity("dgt1", "New Name", None, FAKE_TOKEN, mock_client)
