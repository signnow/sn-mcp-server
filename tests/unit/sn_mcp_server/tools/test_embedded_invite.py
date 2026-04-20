"""Unit tests for embedded_invite module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.embedded_invite import (
    _create_document_embedded_invite,
    _create_document_group_embedded_invite,
    _create_embedded_invite,
)
from sn_mcp_server.tools.models import (
    CreateEmbeddedInviteResponse,
    EmbeddedInviteOrder,
    EmbeddedInviteRecipient,
)


def _make_order(
    order_num: int = 1,
    email: str = "signer@example.com",
    role: str = "Signer",
    delivery_type: str = "email",
) -> EmbeddedInviteOrder:
    """Build a minimal EmbeddedInviteOrder."""
    return EmbeddedInviteOrder(
        order=order_num,
        recipients=[
            EmbeddedInviteRecipient(
                email=email,
                role=role,
                action="sign",
                delivery_type=delivery_type,
            )
        ],
    )


def _make_group(doc_id: str = "doc1", roles: list | None = None) -> MagicMock:
    """Build a minimal document group mock."""
    doc = MagicMock()
    doc.id = doc_id
    doc.roles = roles if roles is not None else ["Signer"]
    group = MagicMock()
    group.documents = [doc]
    return group


class TestCreateDocumentEmbeddedInvite:
    """Test cases for _create_document_embedded_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_happy_path_returns_invite_response(self, mock_client: MagicMock) -> None:
        """Successful call returns CreateEmbeddedInviteResponse with invite_entity=document."""
        invite_item = MagicMock(id="inv_doc_1", email="signer@example.com", order=1)
        mock_client.create_document_embedded_invite.return_value = MagicMock(data=[invite_item])

        result = _create_document_embedded_invite(mock_client, "tok", "doc1", [_make_order()])

        assert isinstance(result, CreateEmbeddedInviteResponse)
        assert result.invite_entity == "document"
        mock_client.create_document_embedded_invite.assert_called_once()

    def test_generates_link_for_link_delivery_type(self, mock_client: MagicMock) -> None:
        """Recipient with delivery_type=link triggers generate_document_embedded_invite_link."""
        invite_item = MagicMock(id="inv_link_1", email="signer@example.com", order=1)
        mock_client.create_document_embedded_invite.return_value = MagicMock(data=[invite_item])
        mock_client.generate_document_embedded_invite_link.return_value = MagicMock(
            data={"link": "https://app.signnow.com/link/abc"}
        )

        result = _create_document_embedded_invite(mock_client, "tok", "doc1", [_make_order(delivery_type="link")])

        mock_client.generate_document_embedded_invite_link.assert_called_once()
        assert len(result.recipient_links) == 1
        assert result.recipient_links[0]["link"] == "https://app.signnow.com/link/abc"
        assert result.recipient_links[0]["role"] == "Signer"
        assert result.recipient_links[0]["document_invite_id"] == "inv_link_1"


class TestCreateDocumentGroupEmbeddedInvite:
    """Test cases for _create_document_group_embedded_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_happy_path_returns_invite_response(self, mock_client: MagicMock) -> None:
        """Successful call returns CreateEmbeddedInviteResponse with invite_entity=document_group."""
        mock_client.create_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_grp_1"))

        result = _create_document_group_embedded_invite(mock_client, "tok", "grp1", [_make_order()], _make_group())

        assert isinstance(result, CreateEmbeddedInviteResponse)
        assert result.document_group_invite_id == "inv_grp_1"
        assert result.invite_entity == "document_group"
        mock_client.create_embedded_invite.assert_called_once()

    def test_generates_link_for_link_delivery_type(self, mock_client: MagicMock) -> None:
        """Recipient with delivery_type=link triggers generate_embedded_invite_link."""
        mock_client.create_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_grp_link"))
        mock_client.generate_embedded_invite_link.return_value = MagicMock(
            data=MagicMock(link="https://app.signnow.com/link/grp")
        )

        result = _create_document_group_embedded_invite(
            mock_client, "tok", "grp1", [_make_order(delivery_type="link")], _make_group()
        )

        mock_client.generate_embedded_invite_link.assert_called_once()
        assert len(result.recipient_links) == 1
        assert result.document_group_invite_id == "inv_grp_link"
        assert result.invite_entity == "document_group"
        assert result.recipient_links[0]["link"] == "https://app.signnow.com/link/grp"
        assert result.recipient_links[0]["role"] == "Signer"


class TestCreateEmbeddedInvite:
    """Test cases for the merged _create_embedded_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    async def test_routes_to_document_group_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Explicit entity_type=document_group dispatches to group path; created_entity_* are None."""
        mock_client.get_document_group.return_value = _make_group()
        mock_client.create_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_grp"))

        result = await _create_embedded_invite("grp1", "document_group", [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"
        assert result.created_entity_id is None
        assert result.created_entity_type is None
        assert result.created_entity_name is None

    async def test_routes_to_document_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Explicit entity_type=document dispatches to document path; created_entity_* are None."""
        mock_client.create_document_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_doc"))

        result = await _create_embedded_invite("doc1", "document", [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document"
        assert result.created_entity_id is None
        assert result.created_entity_type is None
        assert result.created_entity_name is None

    async def test_auto_detects_document_group(self, mock_client: MagicMock) -> None:
        """entity_type=None auto-detects document_group when get_document_group succeeds."""
        mock_client.get_document_group.return_value = _make_group()
        mock_client.create_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_auto_grp"))

        result = await _create_embedded_invite("grp1", None, [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"

    async def test_template_creates_then_invites(self, mock_client: MagicMock) -> None:
        """entity_type=template creates document first, then sends invite on new entity."""
        mock_client.create_document_from_template.return_value = MagicMock(id="new_doc", document_name="New Doc")
        mock_client.create_document_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_tmpl"))

        result = await _create_embedded_invite("tmpl1", "template", [_make_order()], "tok", mock_client, name="New Doc")

        assert result.invite_entity == "document"
        assert result.created_entity_id == "new_doc"
        assert result.created_entity_type == "document"

    async def test_template_group_creates_then_invites(self, mock_client: MagicMock) -> None:
        """entity_type=template_group creates document_group first, then sends invite."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.get_document_group_template.return_value = MagicMock(group_name="My Group")
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "new_grp"})
        mock_client.get_document_group.return_value = _make_group()
        mock_client.create_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_tg"))

        result = await _create_embedded_invite(
            "tg1", "template_group", [_make_order()], "tok", mock_client, name="My Group"
        )

        assert result.invite_entity == "document_group"
        assert result.created_entity_type == "document_group"

    async def test_auto_detects_template_group(self, mock_client: MagicMock) -> None:
        """entity_type=None auto-detects template_group, creates group, then sends invite."""
        # Probe 1 (detection): get_document_group raises 404
        # Probe 2 (dispatch after materialisation): get_document_group succeeds
        mock_client.get_document_group.side_effect = [SignNowAPINotFoundError(), _make_group()]
        mock_client.get_document_group_template.return_value = MagicMock(group_name="Tmpl Grp")
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "new_grp_auto"})
        mock_client.create_embedded_invite.return_value = MagicMock(data=MagicMock(id="inv_tg_auto"))

        result = await _create_embedded_invite("tg_auto", None, [_make_order()], "tok", mock_client, name="My Group")

        assert result.created_entity_type == "document_group"
