"""Unit tests for invite_status module."""

from unittest.mock import MagicMock

import pytest

from signnow_client.models import (
    DocumentFreeformInviteItem,
    DocumentGroupDocumentListItem,
    DocumentGroupSignatureRequest,
    ListDocumentFreeformInvitesResponse,
    ListDocumentGroupDocumentsResponse,
)
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
        assert result.invite_mode == "field"

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
        group.data.freeform_invite = None
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
        assert result.invite_mode == "field"

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
        group.data.freeform_invite = None
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


class TestDocumentFreeformInviteStatus:
    """Document entity with no field_invites — uses list_document_freeform_invites."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_freeform_list_maps_to_invite_status(self, mock_client: MagicMock) -> None:
        doc = _make_document_response("doc_ff", field_invites=[])
        mock_client.get_document.return_value = doc
        mock_client.list_document_freeform_invites.return_value = ListDocumentFreeformInvitesResponse(
            data=[
                DocumentFreeformInviteItem(
                    id="ff_inv_1",
                    status="pending",
                    created=123,
                    email="a@ex.com",
                )
            ],
            meta={},
        )

        result = _get_invite_status("doc_ff", "document", "tok", mock_client)

        assert result.invite_mode == "freeform"
        assert result.invite_id == "ff_inv_1"
        assert result.status == "pending"
        assert result.steps[0].actions[0].email == "a@ex.com"
        assert result.steps[0].actions[0].role is None
        assert result.steps[0].actions[0].document_id == "doc_ff"
        mock_client.list_document_freeform_invites.assert_called_once()
        # default per_page=15, page=1
        mock_client.list_document_freeform_invites.assert_called_with("tok", "doc_ff")

    def test_raises_when_no_field_and_empty_freeform(self, mock_client: MagicMock) -> None:
        doc = _make_document_response("doc_empty", field_invites=[])
        mock_client.get_document.return_value = doc
        mock_client.list_document_freeform_invites.return_value = ListDocumentFreeformInvitesResponse(data=[], meta={})

        with pytest.raises(ValueError, match="doc_empty"):
            _get_invite_status("doc_empty", "document", "tok", mock_client)

    def test_overall_status_is_first_kept_freeform_row_like_field(self, mock_client: MagicMock) -> None:
        """Same as field path: top-level status comes from the first invite row, not a rollup."""
        doc = _make_document_response("doc_mix", field_invites=[])
        mock_client.get_document.return_value = doc
        mock_client.list_document_freeform_invites.return_value = ListDocumentFreeformInvitesResponse(
            data=[
                DocumentFreeformInviteItem(id="a", status="fulfilled", email="x@ex.com"),
                DocumentFreeformInviteItem(id="b", status="pending", email="y@ex.com"),
            ],
            meta={},
        )

        result = _get_invite_status("doc_mix", "document", "tok", mock_client)

        assert result.status == "fulfilled"
        assert result.steps[0].status == "fulfilled"

    def test_skips_freeform_rows_without_email(self, mock_client: MagicMock) -> None:
        """Rows without an email are omitted; invite_id is the first row that has an email."""
        doc = _make_document_response("doc_skip", field_invites=[])
        mock_client.get_document.return_value = doc
        mock_client.list_document_freeform_invites.return_value = ListDocumentFreeformInvitesResponse(
            data=[
                DocumentFreeformInviteItem(id="ff_skip", status="pending", email=None),
                DocumentFreeformInviteItem(id="ff_keep", status="fulfilled", email=" keep@ex.com "),
            ],
            meta={},
        )

        result = _get_invite_status("doc_skip", "document", "tok", mock_client)

        assert result.invite_id == "ff_keep"
        assert result.status == "fulfilled"
        assert result.steps[0].status == "fulfilled"
        assert len(result.steps[0].actions) == 1
        assert result.steps[0].actions[0].email == "keep@ex.com"

    def test_raises_when_all_freeform_rows_missing_email(self, mock_client: MagicMock) -> None:
        doc = _make_document_response("doc_noem", field_invites=[])
        mock_client.get_document.return_value = doc
        mock_client.list_document_freeform_invites.return_value = ListDocumentFreeformInvitesResponse(
            data=[
                DocumentFreeformInviteItem(id="n1", status="pending", email=None),
                DocumentFreeformInviteItem(id="n2", status="pending", email="   "),
            ],
            meta={},
        )

        with pytest.raises(ValueError, match="doc_noem"):
            _get_invite_status("doc_noem", "document", "tok", mock_client)


class TestDocumentGroupFreeformInviteStatus:
    """Document group with field invite_id absent — uses list_document_group_documents."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def _group_freeform_only(self) -> MagicMock:
        g = MagicMock()
        g.data.invite_id = None
        ff = MagicMock()
        ff.id = "ff_dg_1"
        g.data.freeform_invite = ff
        return g

    def test_signature_requests_map_with_emails(self, mock_client: MagicMock) -> None:
        mock_client.get_document_group_v2.return_value = self._group_freeform_only()
        mock_client.list_document_group_documents.return_value = ListDocumentGroupDocumentsResponse(
            data=[
                DocumentGroupDocumentListItem(
                    id="cd19b02135214e6e9ec0a5f40b430e3b6f58873f",
                    signature_requests=[
                        DocumentGroupSignatureRequest(
                            user_id="u1",
                            status="pending",
                            email="a@ex.com",
                        ),
                        DocumentGroupSignatureRequest(
                            user_id="u2",
                            status="pending",
                            email="b@ex.com",
                        ),
                    ],
                )
            ],
            meta={},
        )

        result = _get_invite_status("grp_ff", "document_group", "tok", mock_client)

        assert result.invite_mode == "freeform"
        assert result.invite_id == "ff_dg_1"
        assert result.status == "pending"
        assert len(result.steps[0].actions) == 2
        assert {a.email for a in result.steps[0].actions} == {"a@ex.com", "b@ex.com"}
        mock_client.get_field_invite.assert_not_called()

    def test_raises_when_freeform_but_no_signers(self, mock_client: MagicMock) -> None:
        mock_client.get_document_group_v2.return_value = self._group_freeform_only()
        mock_client.list_document_group_documents.return_value = ListDocumentGroupDocumentsResponse(
            data=[DocumentGroupDocumentListItem(id="d1", signature_requests=[])],
            meta={},
        )

        with pytest.raises(ValueError, match="grp_ns"):
            _get_invite_status("grp_ns", "document_group", "tok", mock_client)

    def test_skips_signature_requests_without_email(self, mock_client: MagicMock) -> None:
        mock_client.get_document_group_v2.return_value = self._group_freeform_only()
        mock_client.list_document_group_documents.return_value = ListDocumentGroupDocumentsResponse(
            data=[
                DocumentGroupDocumentListItem(
                    id="d1",
                    signature_requests=[
                        DocumentGroupSignatureRequest(user_id="u0", status="pending", email=None),
                        DocumentGroupSignatureRequest(user_id="u1", status="fulfilled", email=" ok@ex.com "),
                    ],
                )
            ],
            meta={},
        )

        result = _get_invite_status("grp_email", "document_group", "tok", mock_client)

        assert len(result.steps[0].actions) == 1
        assert result.steps[0].actions[0].email == "ok@ex.com"

    def test_raises_when_all_signature_requests_lack_email(self, mock_client: MagicMock) -> None:
        mock_client.get_document_group_v2.return_value = self._group_freeform_only()
        mock_client.list_document_group_documents.return_value = ListDocumentGroupDocumentsResponse(
            data=[
                DocumentGroupDocumentListItem(
                    id="d1",
                    signature_requests=[
                        DocumentGroupSignatureRequest(user_id="u0", status="pending", email=None),
                    ],
                )
            ],
            meta={},
        )

        with pytest.raises(ValueError, match="with an email"):
            _get_invite_status("grp_noemail", "document_group", "tok", mock_client)

    def test_field_invite_takes_precedence_over_freeform(self, mock_client: MagicMock) -> None:
        """When both invite_id and freeform_invite are set, use field path only."""
        g = MagicMock()
        g.data.invite_id = "field_inv_1"
        ff = MagicMock()
        ff.id = "ff_orphan"
        g.data.freeform_invite = ff
        mock_client.get_document_group_v2.return_value = g

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
        inv = MagicMock()
        inv.id = "field_inv_1"
        inv.status = "pending"
        inv.steps = [step]
        mock_client.get_field_invite.return_value = MagicMock(invite=inv)

        result = _get_invite_status("grp_both", "document_group", "tok", mock_client)

        assert result.invite_mode == "field"
        mock_client.get_field_invite.assert_called_once()
        mock_client.list_document_group_documents.assert_not_called()

    def test_raises_when_no_field_and_no_freeform_id(self, mock_client: MagicMock) -> None:
        g = MagicMock()
        g.data.invite_id = None
        g.data.freeform_invite = None
        mock_client.get_document_group_v2.return_value = g

        with pytest.raises(ValueError, match="grp_none"):
            _get_invite_status("grp_none", "document_group", "tok", mock_client)
