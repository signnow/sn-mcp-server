"""Unit tests for send_invite module."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Context

from sn_mcp_server.tools.models import InviteOrder, InviteRecipient, SendInviteResponse
from sn_mcp_server.tools.send_invite import (
    _send_document_field_invite,
    _send_document_group_field_invite,
    _send_invite,
    _send_invite_from_template,
)


def _make_order(
    order_num: int = 1,
    email: str = "signer@example.com",
    role: str = "Signer",
) -> InviteOrder:
    """Build a minimal InviteOrder."""
    return InviteOrder(
        order=order_num,
        recipients=[
            InviteRecipient(
                email=email,
                role=role,
                action="sign",
                redirect_uri=None,
            )
        ],
    )


class TestSendDocumentFieldInvite:
    """Test cases for _send_document_field_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_happy_path_returns_send_invite_response(self, mock_client: MagicMock) -> None:
        """Test successful document field invite returns SendInviteResponse."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="invite_ok")

        result = _send_document_field_invite(mock_client, "tok", "doc_abc", [_make_order(1, "signer@test.com", "Signer")])

        assert isinstance(result, SendInviteResponse)
        assert result.invite_id == "invite_ok"
        assert result.invite_entity == "document"

    def test_fetches_user_info_for_from_email(self, mock_client: MagicMock) -> None:
        """Test get_user_info is called to determine the from address."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="ok")

        _send_document_field_invite(mock_client, "tok", "doc1", [_make_order()])

        mock_client.get_user_info.assert_called_once_with("tok")

    def test_passes_correct_document_id(self, mock_client: MagicMock) -> None:
        """Test document_id is passed to create_document_field_invite."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="ok")

        _send_document_field_invite(mock_client, "tok", "specific_doc", [_make_order()])

        call_args = mock_client.create_document_field_invite.call_args
        assert call_args[0][1] == "specific_doc"


class TestSendDocumentGroupFieldInvite:
    """Test cases for _send_document_group_field_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def _make_group(self, doc_id: str = "dg_doc1", roles: list | None = None) -> MagicMock:
        """Build a minimal document group mock."""
        doc = MagicMock()
        doc.id = doc_id
        doc.roles = roles if roles is not None else ["Signer"]
        group = MagicMock()
        group.documents = [doc]
        return group

    def test_happy_path_returns_send_invite_response(self, mock_client: MagicMock) -> None:
        """Test successful document group invite returns SendInviteResponse."""
        mock_client.create_field_invite.return_value = MagicMock(id="group_invite_id")
        group = self._make_group("grp_doc1", ["Signer"])
        order = _make_order(1, "signer@example.com", "Signer")

        result = _send_document_group_field_invite(mock_client, "tok", "grp1", [order], group)

        assert isinstance(result, SendInviteResponse)
        assert result.invite_id == "group_invite_id"
        assert result.invite_entity == "document_group"

    def test_ignores_recipients_whose_role_not_in_document(self, mock_client: MagicMock) -> None:
        """Test actions are skipped for roles not present in any document."""
        mock_client.create_field_invite.return_value = MagicMock(id="inv_filtered")
        group = self._make_group("doc1", ["Signer"])  # Only "Signer" role
        order = _make_order(1, "approver@test.com", "Approver")  # "Approver" not in doc

        _send_document_group_field_invite(mock_client, "tok", "grp1", [order], group)

        # create_field_invite should still be called but with empty actions
        call_args = mock_client.create_field_invite.call_args
        request = call_args[0][2]
        # The step was created but actions for "Approver" are omitted
        assert len(request.invite_steps[0].invite_actions) == 0


class TestSendInvite:
    """Test cases for _send_invite entity type auto-detection."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def _configure_group_success(self, mock_client: MagicMock) -> None:
        """Configure mock client to succeed for document group."""
        doc = MagicMock()
        doc.id = "group_doc1"
        doc.roles = ["Signer"]
        group = MagicMock()
        group.documents = [doc]
        mock_client.get_document_group.return_value = group
        mock_client.create_field_invite.return_value = MagicMock(id="grp_invite_x")

    def test_routes_to_document_group_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='document_group' skips auto-detection."""
        self._configure_group_success(mock_client)

        result = _send_invite("grp1", "document_group", [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"
        mock_client.get_document_group.assert_called_once_with("tok", "grp1")

    def test_routes_to_document_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='document' routes to document invite path."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="doc_inv_y")

        result = _send_invite("doc1", "document", [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document"
        assert result.invite_id == "doc_inv_y"

    def test_auto_detects_document_group_when_group_found(self, mock_client: MagicMock) -> None:
        """Test auto-detection picks document_group when get_document_group succeeds."""
        self._configure_group_success(mock_client)

        result = _send_invite("entity1", None, [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"
        mock_client.get_document.assert_not_called()

    def test_auto_detects_document_when_group_lookup_fails(self, mock_client: MagicMock) -> None:
        """Test auto-detection falls back to document when group lookup fails."""
        mock_client.get_document_group.side_effect = Exception("not a group")
        mock_client.get_document.return_value = MagicMock()  # Document found
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@test.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="doc_fallback")

        result = _send_invite("entity_fb", None, [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document"

    def test_raises_value_error_when_entity_not_found(self, mock_client: MagicMock) -> None:
        """Test ValueError raised when entity not found as group or document."""
        mock_client.get_document_group.side_effect = Exception("not group")
        mock_client.get_document.side_effect = Exception("not document")

        with pytest.raises(ValueError, match="entity_gone"):
            _send_invite("entity_gone", None, [_make_order()], "tok", mock_client)


class TestSendInviteFromTemplate:
    """Test cases for _send_invite_from_template async function."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    @pytest.fixture
    def mock_ctx(self) -> AsyncMock:
        """Create a mock FastMCP context."""
        ctx = AsyncMock(spec=Context)
        ctx.report_progress = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    async def test_reports_progress_three_times(self, mock_client: MagicMock, mock_ctx: AsyncMock) -> None:
        """Test that report_progress is called three times during execution."""
        # Setup create_from_template path (template)
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.create_document_from_template.return_value = MagicMock(id="doc_tpl", document_name="From Template")
        mock_client.get_document_group.side_effect = Exception("not a group")
        mock_client.get_document.return_value = MagicMock()
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@test.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="inv_tpl")

        await _send_invite_from_template(
            entity_id="tpl1",
            entity_type="template",
            name="Tpl Doc",
            orders=[_make_order()],
            token="tok",  # noqa: S106
            client=mock_client,
            ctx=mock_ctx,
        )

        assert mock_ctx.report_progress.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_combined_response(self, mock_client: MagicMock, mock_ctx: AsyncMock) -> None:
        """Test returned response combines created entity and invite info."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.create_document_from_template.return_value = MagicMock(id="doc_combo", document_name="Combo")
        mock_client.get_document_group.side_effect = Exception("not group")
        mock_client.get_document.return_value = MagicMock()
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@test.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="combo_inv")

        result = await _send_invite_from_template(
            entity_id="tpl1",
            entity_type="template",
            name="My Template Doc",
            orders=[_make_order()],
            token="tok",  # noqa: S106
            client=mock_client,
            ctx=mock_ctx,
        )

        assert result.created_entity_id == "doc_combo"
        assert result.created_entity_type == "document"
        assert result.created_entity_name == "My Template Doc"
        assert result.invite_id == "combo_inv"
        assert result.invite_entity == "document"
