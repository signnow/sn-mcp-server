"""Unit tests for create_template module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIError, SignNowAPIHTTPError
from signnow_client.models.templates_and_documents import CreateTemplateResponse
from sn_mcp_server.tools.create_template import _is_not_found_error, create_template
from sn_mcp_server.tools.models import CreateTemplateResult


def _http_error(status_code: int, errors: list | None = None) -> SignNowAPIHTTPError:
    """Build a SignNowAPIHTTPError with given status and optional errors list."""
    return SignNowAPIHTTPError(
        message="error",
        status_code=status_code,
        response_data={"errors": errors or []},
    )


def _api_error(status_code: int) -> SignNowAPIError:
    """Build a generic SignNowAPIError with given status."""
    return SignNowAPIError(message="error", status_code=status_code)


class TestIsNotFoundError:
    """Test cases for _is_not_found_error."""

    def test_returns_true_for_400_with_code_65582(self) -> None:
        """Test 400 with SignNow error code 65582 is treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 65582, "message": "Document not found"}])) is True

    def test_returns_true_for_400_with_not_found_message(self) -> None:
        """Test 400 with 'not found' (case-insensitive) in message is treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 99999, "message": "Resource Not Found"}])) is True

    def test_returns_false_for_400_with_other_error(self) -> None:
        """Test 400 with an unrelated error code is not treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 12345, "message": "Validation failed"}])) is False

    def test_returns_false_for_404(self) -> None:
        """Test 404 status is not handled by this helper (separate code path)."""
        assert _is_not_found_error(_http_error(404)) is False

    def test_returns_false_for_500(self) -> None:
        """Test 500 is not treated as not-found."""
        assert _is_not_found_error(_http_error(500)) is False

    def test_returns_false_for_400_with_empty_errors(self) -> None:
        """Test 400 with empty errors list is not treated as not-found."""
        assert _is_not_found_error(_http_error(400, [])) is False


class TestCreateTemplate:
    """Test cases for create_template business logic."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    # ------------------------------------------------------------------
    # Happy paths — explicit entity_type
    # ------------------------------------------------------------------

    def test_document_happy_path(self, mock_client: MagicMock) -> None:
        """Explicit entity_type='document' → calls create_template, returns template_id."""
        mock_client.create_template.return_value = CreateTemplateResponse(id="tmpl_abc")

        result = create_template(mock_client, "tok", "doc1", "My NDA", "document")

        assert isinstance(result, CreateTemplateResult)
        assert result.template_id == "tmpl_abc"
        assert result.template_name == "My NDA"
        assert result.entity_type == "document"
        mock_client.create_template.assert_called_once()
        mock_client.get_document_group_v2.assert_not_called()

    def test_document_group_happy_path(self, mock_client: MagicMock) -> None:
        """Explicit entity_type='document_group' → calls create_document_group_template_from_group, template_id=None."""
        mock_client.create_document_group_template_from_group.return_value = True

        result = create_template(mock_client, "tok", "grp1", "NDA Group", "document_group")

        assert isinstance(result, CreateTemplateResult)
        assert result.template_id is None
        assert result.template_name == "NDA Group"
        assert result.entity_type == "document_group"
        mock_client.create_document_group_template_from_group.assert_called_once()
        mock_client.create_template.assert_not_called()

    # ------------------------------------------------------------------
    # Auto-detection paths
    # ------------------------------------------------------------------

    def test_auto_detect_resolves_document_group(self, mock_client: MagicMock) -> None:
        """entity_type=None + group found → entity_type='document_group'; get_document NOT called."""
        mock_client.get_document_group_v2.return_value = MagicMock()
        mock_client.create_document_group_template_from_group.return_value = True

        result = create_template(mock_client, "tok", "grp1", "NDA Group")

        assert result.entity_type == "document_group"
        mock_client.get_document.assert_not_called()

    def test_auto_detect_falls_back_to_document(self, mock_client: MagicMock) -> None:
        """entity_type=None + group 404 + doc found → entity_type='document'."""
        mock_client.get_document_group_v2.side_effect = _api_error(404)
        mock_client.get_document.return_value = MagicMock()
        mock_client.create_template.return_value = CreateTemplateResponse(id="tmpl_xyz")

        result = create_template(mock_client, "tok", "doc1", "NDA")

        assert result.entity_type == "document"
        assert result.template_id == "tmpl_xyz"

    def test_auto_detect_not_found_raises(self, mock_client: MagicMock) -> None:
        """entity_type=None + both 404 → ValueError with informative message."""
        mock_client.get_document_group_v2.side_effect = _api_error(404)
        mock_client.get_document.side_effect = _api_error(404)

        with pytest.raises(ValueError, match="not found as document or document_group"):
            create_template(mock_client, "tok", "missing_id", "NDA")

    def test_auto_detect_non_404_stops_fallback(self, mock_client: MagicMock) -> None:
        """entity_type=None + group 403 → re-raised immediately; get_document NOT called."""
        mock_client.get_document_group_v2.side_effect = _api_error(403)

        with pytest.raises(SignNowAPIError) as exc_info:
            create_template(mock_client, "tok", "entity_id", "NDA")

        assert exc_info.value.status_code == 403
        mock_client.get_document.assert_not_called()

    def test_auto_detect_document_non_404_reraises(self, mock_client: MagicMock) -> None:
        """entity_type=None + group 404 + document 500 → 500 re-raised."""
        mock_client.get_document_group_v2.side_effect = _api_error(404)
        mock_client.get_document.side_effect = _api_error(500)

        with pytest.raises(SignNowAPIError) as exc_info:
            create_template(mock_client, "tok", "entity_id", "NDA")

        assert exc_info.value.status_code == 500

    # ------------------------------------------------------------------
    # Explicit entity_type error cases
    # ------------------------------------------------------------------

    def test_document_not_found_404(self, mock_client: MagicMock) -> None:
        """entity_type='document' + API 404 → ValueError with entity_id."""
        mock_client.create_template.side_effect = _http_error(404)

        with pytest.raises(ValueError, match="Document not found: bad_doc"):
            create_template(mock_client, "tok", "bad_doc", "NDA", "document")

    def test_document_not_found_400_code_65582(self, mock_client: MagicMock) -> None:
        """entity_type='document' + API 400 with code 65582 → ValueError (SignNow quirk)."""
        mock_client.create_template.side_effect = _http_error(400, [{"code": 65582, "message": "Document not found"}])

        with pytest.raises(ValueError, match="Document not found: bad_doc"):
            create_template(mock_client, "tok", "bad_doc", "NDA", "document")

    def test_document_no_permission(self, mock_client: MagicMock) -> None:
        """entity_type='document' + 403 → permission ValueError."""
        mock_client.create_template.side_effect = _http_error(403)

        with pytest.raises(ValueError, match="No permission to templatize document: doc1"):
            create_template(mock_client, "tok", "doc1", "NDA", "document")

    def test_document_group_not_found(self, mock_client: MagicMock) -> None:
        """entity_type='document_group' + API 404 → ValueError with entity_id."""
        mock_client.create_document_group_template_from_group.side_effect = _http_error(404)

        with pytest.raises(ValueError, match="Document group not found: bad_grp"):
            create_template(mock_client, "tok", "bad_grp", "NDA Group", "document_group")

    def test_document_group_no_permission(self, mock_client: MagicMock) -> None:
        """entity_type='document_group' + 403 → permission ValueError."""
        mock_client.create_document_group_template_from_group.side_effect = _http_error(403)

        with pytest.raises(ValueError, match="No permission to templatize document group: grp1"):
            create_template(mock_client, "tok", "grp1", "NDA", "document_group")

    def test_document_other_api_error_reraises(self, mock_client: MagicMock) -> None:
        """entity_type='document' + 500 → re-raised as-is."""
        mock_client.create_template.side_effect = _http_error(500)

        with pytest.raises(SignNowAPIHTTPError) as exc_info:
            create_template(mock_client, "tok", "doc1", "NDA", "document")

        assert exc_info.value.status_code == 500

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def test_empty_template_name_raises(self, mock_client: MagicMock) -> None:
        """Blank template_name → ValueError before any API call."""
        with pytest.raises(ValueError, match="template_name must not be empty"):
            create_template(mock_client, "tok", "doc1", "")

        mock_client.create_template.assert_not_called()
        mock_client.get_document_group_v2.assert_not_called()

    def test_whitespace_template_name_raises(self, mock_client: MagicMock) -> None:
        """Whitespace-only template_name → ValueError before any API call."""
        with pytest.raises(ValueError, match="template_name must not be empty"):
            create_template(mock_client, "tok", "doc1", "   ")

    def test_empty_entity_id_raises(self, mock_client: MagicMock) -> None:
        """Blank entity_id → ValueError before any API call."""
        with pytest.raises(ValueError, match="entity_id must not be empty"):
            create_template(mock_client, "tok", "", "NDA")

        mock_client.create_template.assert_not_called()

    def test_invalid_entity_type_raises(self, mock_client: MagicMock) -> None:
        """entity_type='template' (wrong value) → ValueError before any API call."""
        with pytest.raises(ValueError, match="Invalid entity_type 'template'"):
            create_template(mock_client, "tok", "doc1", "NDA", "template")  # type: ignore[arg-type]

        mock_client.create_template.assert_not_called()
