"""Unit tests for create_from_template module."""

from unittest.mock import MagicMock

import pytest

from signnow_client.exceptions import SignNowAPIHTTPError
from signnow_client.models.document_groups import DocumentGroupTemplate
from sn_mcp_server.tools.create_from_template import (
    _create_document_from_template,
    _create_document_group_from_template,
    _create_from_template,
    _find_template_group,
    _is_not_found_error,
)
from sn_mcp_server.tools.models import CreateFromTemplateResponse


def _make_template_group(template_group_id: str = "tg123", name: str = "My Group") -> DocumentGroupTemplate:
    """Build a minimal DocumentGroupTemplate."""
    return DocumentGroupTemplate(
        folder_id=None,
        last_updated=0,
        template_group_id=template_group_id,
        template_group_name=name,
        owner_email="owner@example.com",
        templates=[],
        is_prepared=True,
    )


def _http_error(status_code: int, errors: list | None = None) -> SignNowAPIHTTPError:
    """Build a SignNowAPIHTTPError with given status and optional errors list."""
    return SignNowAPIHTTPError(
        message="error",
        status_code=status_code,
        response_data={"errors": errors or []},
    )


class TestIsNotFoundError:
    """Test cases for _is_not_found_error."""

    def test_returns_true_for_400_with_code_65582(self) -> None:
        """Test 400 with SignNow error code 65582 is treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 65582, "message": "Document not found"}])) is True

    def test_returns_true_for_400_with_not_found_message(self) -> None:
        """Test 400 with 'not found' (case-insensitive) in message is treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 99999, "message": "Resource not found"}])) is True

    def test_returns_true_for_400_with_unable_to_find_message(self) -> None:
        """Test 400 with 'unable to find' message (documentgroup/template endpoint) is treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 65582, "message": "unable to find document group template"}])) is True

    def test_returns_false_for_400_with_other_error(self) -> None:
        """Test 400 with an unrelated error code is not treated as not-found."""
        assert _is_not_found_error(_http_error(400, [{"code": 12345, "message": "Validation failed"}])) is False

    def test_returns_false_for_500(self) -> None:
        """Test 500 is not treated as not-found."""
        assert _is_not_found_error(_http_error(500)) is False

    def test_returns_false_for_400_with_empty_errors(self) -> None:
        """Test 400 with no errors list is not treated as not-found."""
        assert _is_not_found_error(_http_error(400, [])) is False


class TestCreateDocumentFromTemplate:
    """Test cases for _create_document_from_template."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_creates_document_with_provided_name(self, mock_client: MagicMock) -> None:
        """Test successful creation uses provided name."""
        mock_client.create_document_from_template.return_value = MagicMock(id="doc999", document_name="Server Name")

        result = _create_document_from_template(mock_client, "tok", "tmpl1", "Custom Name")

        assert isinstance(result, CreateFromTemplateResponse)
        assert result.entity_id == "doc999"
        assert result.entity_type == "document"
        assert result.name == "Custom Name"

    def test_falls_back_to_response_document_name(self, mock_client: MagicMock) -> None:
        """Test name falls back to response.document_name when caller provides none."""
        mock_client.create_document_from_template.return_value = MagicMock(id="doc888", document_name="Response Name")

        result = _create_document_from_template(mock_client, "tok", "tmpl1", None)

        assert result.name == "Response Name"

    def test_falls_back_to_id_prefix_when_no_name(self, mock_client: MagicMock) -> None:
        """Test name falls back to Document_<id[:8]> when both name and document_name are missing."""
        mock_client.create_document_from_template.return_value = MagicMock(id="abcdef1234567890", document_name=None)

        result = _create_document_from_template(mock_client, "tok", "tmpl1", None)

        assert result.name == "Document_abcdef12"

    def test_404_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that a 404 HTTP error propagates as-is (not converted to ValueError)."""
        mock_client.create_document_from_template.side_effect = _http_error(404)

        with pytest.raises(SignNowAPIHTTPError):
            _create_document_from_template(mock_client, "tok", "tmpl_missing", None)

    def test_400_with_code_65582_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that 400 'Document not found' (code 65582) is converted to ValueError."""
        mock_client.create_document_from_template.side_effect = _http_error(400, [{"code": 65582, "message": "Document not found"}])

        with pytest.raises(ValueError, match="tmpl_bad"):
            _create_document_from_template(mock_client, "tok", "tmpl_bad", None)

    def test_unrelated_http_error_propagates(self, mock_client: MagicMock) -> None:
        """Test that non-not-found HTTP errors propagate as-is."""
        mock_client.create_document_from_template.side_effect = _http_error(500, [{"code": 0, "message": "Server error"}])

        with pytest.raises(SignNowAPIHTTPError):
            _create_document_from_template(mock_client, "tok", "tmpl_server_err", None)


class TestCreateDocumentGroupFromTemplate:
    """Test cases for _create_document_group_from_template."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_raises_when_name_missing(self, mock_client: MagicMock) -> None:
        """Test that missing name raises ValueError."""
        with pytest.raises(ValueError, match="name is required"):
            _create_document_group_from_template(mock_client, "tok", "tg1", "")

    def test_400_not_found_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that 400 not-found from create_document_group_from_template raises ValueError."""
        mock_client.create_document_group_from_template.side_effect = _http_error(400, [{"code": 65582, "message": "unable to find document group template"}])

        with pytest.raises(ValueError, match="tg_missing"):
            _create_document_group_from_template(mock_client, "tok", "tg_missing", "My Group")

    def test_unrelated_http_error_propagates(self, mock_client: MagicMock) -> None:
        """Test that non-not-found HTTP errors propagate as-is."""
        mock_client.create_document_group_from_template.side_effect = _http_error(500, [{"code": 0, "message": "Server error"}])

        with pytest.raises(SignNowAPIHTTPError):
            _create_document_group_from_template(mock_client, "tok", "tg1", "My Group")

    def test_extracts_unique_id_from_response(self, mock_client: MagicMock) -> None:
        """Test ID is extracted from response data unique_id key."""
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "grp_uid_123"})

        result = _create_document_group_from_template(mock_client, "tok", "tg1", "Group Alpha")

        assert result.entity_id == "grp_uid_123"
        assert result.entity_type == "document_group"
        assert result.name == "Group Alpha"

    def test_extracts_id_from_response(self, mock_client: MagicMock) -> None:
        """Test ID is extracted from response data id key as fallback."""
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"id": "grp_id_456"})

        result = _create_document_group_from_template(mock_client, "tok", "tg1", "Group Beta")

        assert result.entity_id == "grp_id_456"

    def test_extracts_group_id_from_response(self, mock_client: MagicMock) -> None:
        """Test ID is extracted from response data group_id key as second fallback."""
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"group_id": "grp_gid_789"})

        result = _create_document_group_from_template(mock_client, "tok", "tg1", "Group Gamma")

        assert result.entity_id == "grp_gid_789"


class TestFindTemplateGroup:
    """Test cases for _find_template_group."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_returns_group_when_id_matches(self, mock_client: MagicMock) -> None:
        """Test returns matching template group."""
        group = _make_template_group("tg-match")
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[group, _make_template_group("tg-other")])

        result = _find_template_group("tg-match", "tok", mock_client)

        assert result is group

    def test_returns_none_when_not_found(self, mock_client: MagicMock) -> None:
        """Test returns None when ID not found in template groups."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[_make_template_group("tg-other")])

        result = _find_template_group("tg-missing", "tok", mock_client)

        assert result is None

    def test_returns_none_for_empty_list(self, mock_client: MagicMock) -> None:
        """Test returns None when template groups list is empty."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])

        result = _find_template_group("tg-any", "tok", mock_client)

        assert result is None


class TestCreateFromTemplate:
    """Test cases for _create_from_template entity type resolution and retry logic."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_creates_document_when_explicit_template_type(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='template' routes to document creation."""
        mock_client.create_document_from_template.return_value = MagicMock(id="doc_explicit", document_name="Doc")

        result = _create_from_template("tmpl1", "template", "My Doc", "tok", mock_client)

        assert result.entity_type == "document"
        assert result.entity_id == "doc_explicit"

    def test_creates_group_when_explicit_template_group_type(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='template_group' routes to document_group creation."""
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "grpX"})

        result = _create_from_template("tg1", "template_group", "My Group", "tok", mock_client)

        assert result.entity_type == "document_group"
        assert result.entity_id == "grpX"

    def test_auto_detects_template_group_when_found_in_list(self, mock_client: MagicMock) -> None:
        """Test auto-detection resolves to template_group when found in list scan."""
        group = _make_template_group("auto-tg", "Auto Group")
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[group])
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "grp_auto"})

        result = _create_from_template("auto-tg", None, "Auto Group", "tok", mock_client)

        assert result.entity_type == "document_group"

    def test_auto_detects_template_when_not_in_group_list(self, mock_client: MagicMock) -> None:
        """Test auto-detection resolves to template when ID not in list and template create succeeds."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.create_document_from_template.return_value = MagicMock(id="doc_auto", document_name="Auto Doc")

        result = _create_from_template("tmpl_auto", None, "Auto Doc", "tok", mock_client)

        assert result.entity_type == "document"

    def test_auto_detected_template_raises_value_error_on_400_not_found(self, mock_client: MagicMock) -> None:
        """Test 400 not-found from auto-detected template raises ValueError immediately."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.create_document_from_template.side_effect = _http_error(400, [{"code": 65582, "message": "Document not found"}])

        with pytest.raises(ValueError, match="tg-unlisted"):
            _create_from_template("tg-unlisted", None, None, "tok", mock_client)

        mock_client.create_document_group_from_template.assert_not_called()

    def test_explicit_template_type_raises_value_error_on_400_not_found(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='template' raises ValueError on 400 not-found."""
        mock_client.create_document_from_template.side_effect = _http_error(400, [{"code": 65582, "message": "Document not found"}])

        with pytest.raises(ValueError, match="tmpl_explicit"):
            _create_from_template("tmpl_explicit", "template", None, "tok", mock_client)

        mock_client.create_document_group_from_template.assert_not_called()

    def test_explicit_template_group_type_name_lookup_not_found_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test that 400 not-found from get_document_group_template name lookup raises ValueError.

        Production case: explicit entity_type='template_group', no name provided,
        get_document_group_template returns 400 code 65582 because the ID doesn't exist.
        """
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.get_document_group_template.side_effect = _http_error(400, [{"code": 65582, "message": "unable to find document group template"}])

        with pytest.raises(ValueError, match="tg-bad-id"):
            _create_from_template("tg-bad-id", "template_group", None, "tok", mock_client)

        mock_client.create_document_group_from_template.assert_not_called()

    def test_uses_template_group_name_when_name_not_provided(self, mock_client: MagicMock) -> None:
        """Test name is sourced from found template group when not explicitly provided."""
        group = _make_template_group("tg-name", "Group Name From API")
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[group])
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "grp_nm"})

        result = _create_from_template("tg-name", None, None, "tok", mock_client)

        assert result.name == "Group Name From API"
