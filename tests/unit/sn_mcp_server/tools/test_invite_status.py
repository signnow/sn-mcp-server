"""Unit tests for invite_status module."""

from unittest.mock import MagicMock

import pytest

from sn_mcp_server.tools.invite_status import (
    _get_document_group_status,
    _get_document_status,
    _get_invite_status,
)
from sn_mcp_server.tools.models import InviteStatus


def _make_field_invite(
    invite_id: str = "fi1",
    email: str = "signer@example.com",
    status: str = "pending",
    role: str = "Signer",
) -> MagicMock:
    """Build a minimal field invite mock."""
    fi = MagicMock()
    fi.id = invite_id
    fi.email = email
    fi.status = status
    fi.role = role
    return fi


def _make_document_response(
    doc_id: str = "doc1",
    field_invites: list | None = None,
) -> MagicMock:
    """Build a minimal document response mock."""
    doc = MagicMock()
    doc.id = doc_id
    doc.field_invites = field_invites if field_invites is not None else []
    return doc


class TestGetDocumentStatus:
    """Test cases for _get_document_status."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_transforms_field_invites_to_invite_status(self, mock_client: MagicMock) -> None:
        """Test that field invites are transformed to InviteStatus with actions."""
        fi = _make_field_invite("invite123", "signer@example.com", "pending", "Signer")
        doc = _make_document_response("doc1", [fi])

        result = _get_document_status(mock_client, "tok", doc)

        assert isinstance(result, InviteStatus)
        assert result.invite_id == "invite123"
        assert result.status == "pending"
        assert len(result.steps) == 1
        assert len(result.steps[0].actions) == 1
        assert result.steps[0].actions[0].email == "signer@example.com"
        assert result.steps[0].actions[0].role == "Signer"
        assert result.steps[0].actions[0].document_id == "doc1"
        assert result.steps[0].actions[0].action == "sign"

    def test_raises_when_no_field_invites(self, mock_client: MagicMock) -> None:
        """Test ValueError raised when document has no field invites."""
        doc = _make_document_response("doc_empty", [])

        with pytest.raises(ValueError, match="doc_empty"):
            _get_document_status(mock_client, "tok", doc)

    def test_skips_field_invite_without_email(self, mock_client: MagicMock) -> None:
        """Test field invites with no email are excluded from actions."""
        fi_no_email = _make_field_invite("fi_no_email", "", "pending", "Reviewer")
        fi_no_email.email = None
        fi_with_email = _make_field_invite("fi_ok", "ok@example.com", "pending", "Signer")
        doc = _make_document_response("doc2", [fi_no_email, fi_with_email])

        result = _get_document_status(mock_client, "tok", doc)

        assert len(result.steps[0].actions) == 1
        assert result.steps[0].actions[0].email == "ok@example.com"

    def test_invite_id_is_first_field_invite_id(self, mock_client: MagicMock) -> None:
        """Test invite_id uses the first field invite's id."""
        fi1 = _make_field_invite("first_fi", "a@test.com", "fulfilled", "Signer")
        fi2 = _make_field_invite("second_fi", "b@test.com", "pending", "Reviewer")
        doc = _make_document_response("doc3", [fi1, fi2])

        result = _get_document_status(mock_client, "tok", doc)

        assert result.invite_id == "first_fi"


class TestGetDocumentGroupStatus:
    """Test cases for _get_document_group_status."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def _make_group_response(self, invite_id: str | None = "group_invite_1") -> MagicMock:
        """Build a mock document group response."""
        group = MagicMock()
        group.data.invite_id = invite_id
        return group

    def _make_field_invite_response(
        self,
        invite_id: str = "group_invite_1",
        status: str = "pending",
        steps: list | None = None,
    ) -> MagicMock:
        """Build a mock get_field_invite response."""
        invite = MagicMock()
        invite.id = invite_id
        invite.status = status
        invite.steps = steps if steps is not None else []
        response = MagicMock()
        response.invite = invite
        return response

    def test_raises_when_no_invite_id(self, mock_client: MagicMock) -> None:
        """Test ValueError raised when group has no invite_id."""
        group_data = self._make_group_response(invite_id=None)

        with pytest.raises(ValueError, match="group_abc"):
            _get_document_group_status(mock_client, "tok", group_data, "group_abc")

    def test_returns_invite_status_with_steps(self, mock_client: MagicMock) -> None:
        """Test successful transformation of group invite into InviteStatus with steps."""
        action = MagicMock()
        action.action = "sign"
        action.email = "signer@test.com"
        action.document_id = "doc1"
        action.status = "pending"
        action.role_name = "Signer"

        step = MagicMock()
        step.status = "pending"
        step.order = 1
        step.actions = [action]

        invite_response = self._make_field_invite_response(invite_id="group_invite_1", status="pending", steps=[step])
        mock_client.get_field_invite.return_value = invite_response
        group_data = self._make_group_response("group_invite_1")

        result = _get_document_group_status(mock_client, "tok", group_data, "group1")

        assert isinstance(result, InviteStatus)
        assert result.invite_id == "group_invite_1"
        assert result.status == "pending"
        assert len(result.steps) == 1
        assert result.steps[0].order == 1
        assert result.steps[0].actions[0].email == "signer@test.com"

    def test_filters_actions_without_email(self, mock_client: MagicMock) -> None:
        """Test actions with no email are excluded from step actions."""
        action_no_email = MagicMock()
        action_no_email.email = None

        action_with_email = MagicMock()
        action_with_email.action = "sign"
        action_with_email.email = "valid@test.com"
        action_with_email.document_id = "d1"
        action_with_email.status = "pending"
        action_with_email.role_name = "Signer"

        step = MagicMock()
        step.status = "pending"
        step.order = 1
        step.actions = [action_no_email, action_with_email]

        invite_response = self._make_field_invite_response(steps=[step])
        mock_client.get_field_invite.return_value = invite_response
        group_data = self._make_group_response("inv1")

        result = _get_document_group_status(mock_client, "tok", group_data, "grpX")

        assert len(result.steps[0].actions) == 1
        assert result.steps[0].actions[0].email == "valid@test.com"


class TestGetInviteStatus:
    """Test cases for _get_invite_status entity type resolution."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def _configure_group_success(self, mock_client: MagicMock, invite_id: str = "inv1") -> None:
        """Configure mock client to succeed on get_document_group_v2."""
        group = MagicMock()
        group.data.invite_id = invite_id
        mock_client.get_document_group_v2.return_value = group

        action = MagicMock()
        action.action = "sign"
        action.email = "s@test.com"
        action.document_id = "d1"
        action.status = "pending"
        action.role_name = "Signer"

        step = MagicMock()
        step.status = "pending"
        step.order = 1
        step.actions = [action]

        invite = MagicMock()
        invite.id = invite_id
        invite.status = "pending"
        invite.steps = [step]
        fi_response = MagicMock()
        fi_response.invite = invite
        mock_client.get_field_invite.return_value = fi_response

    def test_returns_group_status_when_entity_type_is_document_group(self, mock_client: MagicMock) -> None:
        """Test explicit document_group entity_type routes to group status path."""
        self._configure_group_success(mock_client)

        result = _get_invite_status("grp1", "document_group", "tok", mock_client)

        assert isinstance(result, InviteStatus)
        mock_client.get_document_group_v2.assert_called_once_with("tok", "grp1")

    def test_returns_document_status_when_entity_type_is_document(self, mock_client: MagicMock) -> None:
        """Test explicit document entity_type routes to document status path."""
        fi = _make_field_invite("fi_x", "doc_signer@example.com", "fulfilled", "Signer")
        doc = _make_document_response("doc_explicit", [fi])
        mock_client.get_document.return_value = doc

        result = _get_invite_status("doc_explicit", "document", "tok", mock_client)

        assert isinstance(result, InviteStatus)
        mock_client.get_document.assert_called_once_with("tok", "doc_explicit")

    def test_auto_detects_document_group_first(self, mock_client: MagicMock) -> None:
        """Test auto-detection tries document_group before document."""
        self._configure_group_success(mock_client, "inv_auto")

        result = _get_invite_status("entity_auto", None, "tok", mock_client)

        assert isinstance(result, InviteStatus)
        mock_client.get_document_group_v2.assert_called_once()
        mock_client.get_document.assert_not_called()

    def test_auto_detects_falls_back_to_document(self, mock_client: MagicMock) -> None:
        """Test auto-detection falls back to document when group lookup fails."""
        mock_client.get_document_group_v2.side_effect = Exception("not a group")
        fi = _make_field_invite("fi_fb", "fallback@test.com", "pending", "Signer")
        doc = _make_document_response("entity_fb", [fi])
        mock_client.get_document.return_value = doc

        result = _get_invite_status("entity_fb", None, "tok", mock_client)

        assert isinstance(result, InviteStatus)
        mock_client.get_document.assert_called_once_with("tok", "entity_fb")

    def test_raises_when_entity_not_found_in_either_type(self, mock_client: MagicMock) -> None:
        """Test ValueError raised when entity not found as group or document."""
        mock_client.get_document_group_v2.side_effect = Exception("not group")
        mock_client.get_document.side_effect = Exception("not doc")

        with pytest.raises(ValueError, match="entity_gone"):
            _get_invite_status("entity_gone", None, "tok", mock_client)
