"""Unit tests for rename_entity tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from signnow_client.exceptions import SignNowAPIHTTPError
from sn_mcp_server.tools.models import RenameEntityResponse
from sn_mcp_server.tools.rename_entity import _rename_entity

FAKE_TOKEN = "test-token"  # noqa: S105
_UTILS_PATH = "sn_mcp_server.tools.rename_entity._detect_entity_type"


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

    @pytest.mark.parametrize(
        "detected_type,expected_client_method",
        [
            ("document_group", "rename_document_group"),
            ("template_group", "rename_template_group"),
            ("document", "rename_document"),
            ("template", "rename_document"),
        ],
    )
    def test_auto_detect_delegates_to_utils(
        self,
        mock_client: MagicMock,
        detected_type: str,
        expected_client_method: str,
    ) -> None:
        """Auto-detect (entity_type=None) uses _detect_entity_type from utils for all four types."""
        with patch(_UTILS_PATH, return_value=detected_type) as mock_detect:
            result = _rename_entity("id1", "New Name", None, FAKE_TOKEN, mock_client)

        mock_detect.assert_called_once_with("id1", FAKE_TOKEN, mock_client)
        getattr(mock_client, expected_client_method).assert_called_once()
        assert result.entity_type == detected_type

    def test_invalid_entity_type_raises(self, mock_client: MagicMock) -> None:
        """Raises ValueError for unsupported entity_type."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            _rename_entity("id1", "New Name", "folder", FAKE_TOKEN, mock_client)  # type: ignore[arg-type]

    def test_auto_detect_propagates_not_found_error(self, mock_client: MagicMock) -> None:
        """Propagates SignNowAPIHTTPError from _detect_entity_type when entity not found."""
        not_found = SignNowAPIHTTPError("Not found", 404)
        with patch(_UTILS_PATH, side_effect=not_found):
            with pytest.raises(SignNowAPIHTTPError):
                _rename_entity("bad_id", "Name", None, FAKE_TOKEN, mock_client)
