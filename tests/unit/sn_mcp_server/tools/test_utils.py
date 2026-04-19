"""Unit tests for utils module."""

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIError, SignNowAPIHTTPError, SignNowAPINotFoundError
from sn_mcp_server.tools.utils import _detect_entity_type


class TestDetectEntityType:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_group_detected_first(self, mock_client: MagicMock) -> None:
        """Returns 'document_group' when get_document_group succeeds; other probes never called."""
        mock_client.get_document_group.return_value = MagicMock()

        result = _detect_entity_type("grp1", "tok", mock_client)

        assert result == "document_group"
        mock_client.get_document_group_template.assert_not_called()
        mock_client.get_document.assert_not_called()

    def test_template_group_fallback(self, mock_client: MagicMock) -> None:
        """Returns 'template_group' when group not found but template group succeeds."""
        mock_client.get_document_group.side_effect = SignNowAPIHTTPError(message="", status_code=400, response_data={"errors": [{"code": 65582, "message": ""}]})
        mock_client.get_document_group_template.return_value = MagicMock()

        result = _detect_entity_type("tg1", "tok", mock_client)

        assert result == "template_group"
        mock_client.get_document.assert_not_called()

    def test_document_fallback(self, mock_client: MagicMock) -> None:
        """Returns 'document' when group and template-group both 404 and document.template is falsy."""
        mock_client.get_document_group.side_effect = SignNowAPINotFoundError()
        mock_client.get_document_group_template.side_effect = SignNowAPINotFoundError()
        mock_client.get_document.return_value = MagicMock(template=False)

        result = _detect_entity_type("doc1", "tok", mock_client)

        assert result == "document"

    def test_template_detected_via_document(self, mock_client: MagicMock) -> None:
        """Returns 'template' when group and template-group both 404 and document.template is truthy."""
        mock_client.get_document_group.side_effect = SignNowAPINotFoundError()
        mock_client.get_document_group_template.side_effect = SignNowAPINotFoundError()
        mock_client.get_document.return_value = MagicMock(template=True)

        result = _detect_entity_type("tmpl1", "tok", mock_client)

        assert result == "template"

    def test_non_404_document_error_propagates(self, mock_client: MagicMock) -> None:
        """Non-404 error from get_document propagates immediately."""
        mock_client.get_document_group.side_effect = SignNowAPINotFoundError()
        mock_client.get_document_group_template.side_effect = SignNowAPINotFoundError()
        mock_client.get_document.side_effect = SignNowAPIError("server error", status_code=500)

        with pytest.raises(SignNowAPIError) as exc_info:
            _detect_entity_type("any_id", "tok", mock_client)

        assert exc_info.value.status_code == 500
