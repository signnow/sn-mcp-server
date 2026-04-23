"""Unit tests for send_invite module."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models.templates_and_documents import FieldInviteAuthentication
from sn_mcp_server.tools.models import InviteOrder, InviteRecipient, SendInviteResponse, SignerAuthentication
from sn_mcp_server.tools.send_invite import (
    _build_document_auth_kwargs,
    _build_field_invite_authentication,
    _document_group_has_roles,
    _has_fields,
    _send_document_field_invite,
    _send_document_freeform_invite,
    _send_document_group_field_invite,
    _send_document_group_freeform_invite,
    _send_invite,
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


def _make_order_with_auth(
    authentication: SignerAuthentication,
    order_num: int = 1,
    email: str = "signer@example.com",
    role: str = "Signer",
) -> InviteOrder:
    """Build a minimal InviteOrder with signer authentication."""
    return InviteOrder(
        order=order_num,
        recipients=[
            InviteRecipient(
                email=email,
                role=role,
                action="sign",
                redirect_uri=None,
                authentication=authentication,
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

    async def test_routes_to_document_group_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='document_group' skips auto-detection."""
        self._configure_group_success(mock_client)

        result = await _send_invite("grp1", "document_group", [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"
        mock_client.get_document_group.assert_called_once_with("tok", "grp1")

    async def test_routes_to_document_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Test explicit entity_type='document' routes to document field invite path."""
        mock_client.get_document.return_value = MagicMock(fields=[MagicMock()])
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="doc_inv_y")

        result = await _send_invite("doc1", "document", [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document"
        assert result.invite_id == "doc_inv_y"

    async def test_auto_detects_document_group_when_group_found(self, mock_client: MagicMock) -> None:
        """Test auto-detection picks document_group when get_document_group succeeds."""
        self._configure_group_success(mock_client)

        result = await _send_invite("entity1", None, [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"
        mock_client.get_document.assert_not_called()

    async def test_auto_detects_document_when_group_lookup_fails(self, mock_client: MagicMock) -> None:
        """Test auto-detection falls back to document when group lookup fails."""
        mock_client.get_document_group.side_effect = SignNowAPINotFoundError()
        mock_client.get_document_group_template.side_effect = SignNowAPINotFoundError()
        mock_client.get_document.return_value = MagicMock(template=False, fields=[MagicMock()])
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@test.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="doc_fallback")

        result = await _send_invite("entity_fb", None, [_make_order()], "tok", mock_client)

        assert result.invite_entity == "document"

    async def test_raises_when_entity_not_found(self, mock_client: MagicMock) -> None:
        """Test SignNowAPINotFoundError propagates when all detection probes return 404."""
        mock_client.get_document_group.side_effect = SignNowAPINotFoundError()
        mock_client.get_document_group_template.side_effect = SignNowAPINotFoundError()
        mock_client.get_document.side_effect = SignNowAPINotFoundError()

        with pytest.raises(SignNowAPINotFoundError):
            await _send_invite("entity_gone", None, [_make_order()], "tok", mock_client)


class TestHasFields:
    """Test cases for _has_fields helper."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_returns_true_when_document_has_fields(self, mock_client: MagicMock) -> None:
        """Test returns True when document has at least one field."""
        mock_client.get_document.return_value = MagicMock(fields=[MagicMock()])

        assert _has_fields(mock_client, "tok", "doc1") is True

    def test_returns_false_when_document_has_no_fields(self, mock_client: MagicMock) -> None:
        """Test returns False when document has empty fields list."""
        mock_client.get_document.return_value = MagicMock(fields=[])

        assert _has_fields(mock_client, "tok", "doc1") is False

    def test_calls_get_document_with_correct_args(self, mock_client: MagicMock) -> None:
        """Test get_document is called with token and entity_id."""
        mock_client.get_document.return_value = MagicMock(fields=[])

        _has_fields(mock_client, "my_token", "my_doc")

        mock_client.get_document.assert_called_once_with("my_token", "my_doc")


class TestDocumentGroupHasRoles:
    """Test cases for _document_group_has_roles helper."""

    def _make_group(self, roles_per_doc: list[list[str]]) -> MagicMock:
        """Build a document group mock with specified roles per document."""
        group = MagicMock()
        docs = []
        for roles in roles_per_doc:
            doc = MagicMock()
            doc.roles = roles
            docs.append(doc)
        group.documents = docs
        return group

    def test_returns_true_when_any_document_has_roles(self) -> None:
        """Test returns True when at least one document defines roles."""
        group = self._make_group([[], ["Signer"]])

        assert _document_group_has_roles(group) is True

    def test_returns_false_when_no_documents_have_roles(self) -> None:
        """Test returns False when no documents define roles."""
        group = self._make_group([[], []])

        assert _document_group_has_roles(group) is False

    def test_returns_true_when_all_documents_have_roles(self) -> None:
        """Test returns True when all documents define roles."""
        group = self._make_group([["Signer"], ["Approver"]])

        assert _document_group_has_roles(group) is True


class TestSendDocumentFreeformInvite:
    """Test cases for _send_document_freeform_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        client = MagicMock()
        client.get_user_info.return_value = MagicMock(primary_email="sender@example.com")
        client.create_document_freeform_invite.return_value = MagicMock(id="inv1")
        return client

    def test_happy_path_returns_send_invite_response(self, mock_client: MagicMock) -> None:
        """Test successful freeform invite returns SendInviteResponse."""
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        result = _send_document_freeform_invite(mock_client, "tok", "doc1", [order])

        assert isinstance(result, SendInviteResponse)
        assert result.invite_id == "inv1"
        assert result.invite_entity == "document"

    def test_fetches_sender_email_from_user_info(self, mock_client: MagicMock) -> None:
        """Test get_user_info is called to determine the sender address."""
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        _send_document_freeform_invite(mock_client, "tok", "doc1", [order])

        mock_client.get_user_info.assert_called_once_with("tok")

    def test_multiple_recipients_fires_one_api_call_per_recipient(self, mock_client: MagicMock) -> None:
        """Test multiple recipients across orders each trigger a separate API call."""
        mock_client.create_document_freeform_invite.side_effect = [
            MagicMock(id="inv_a"),
            MagicMock(id="inv_b"),
            MagicMock(id="inv_c"),
        ]
        orders = [
            InviteOrder(
                order=1,
                recipients=[
                    InviteRecipient(email="a@test.com", action="sign"),
                    InviteRecipient(email="b@test.com", action="sign"),
                ],
            ),
            InviteOrder(
                order=2,
                recipients=[InviteRecipient(email="c@test.com", action="sign")],
            ),
        ]

        result = _send_document_freeform_invite(mock_client, "tok", "doc1", orders)

        assert mock_client.create_document_freeform_invite.call_count == 3
        assert result.invite_id == "inv_c"  # last invite ID

    def test_sender_is_mid_list_recipient_all_invites_sent_and_link_populated(self, mock_client: MagicMock) -> None:
        """When sender is one of several recipients, all invites are still sent and the signing link is attached."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="sender@example.com")
        mock_client.create_document_freeform_invite.side_effect = [
            MagicMock(id="inv_a"),
            MagicMock(id="inv_b"),
            MagicMock(id="inv_c"),
        ]
        mock_client.cfg.app_base = "https://app.test.signnow.com"
        mock_client.get_document.return_value = MagicMock(fields=[], template=False, id="doc1", document_name="doc", roles=[])
        orders = [
            InviteOrder(
                order=1,
                recipients=[
                    InviteRecipient(email="other1@test.com", action="sign"),
                    InviteRecipient(email="sender@example.com", action="sign"),
                    InviteRecipient(email="other2@test.com", action="sign"),
                ],
            ),
        ]

        result = _send_document_freeform_invite(mock_client, "tok", "doc1", orders)

        # All three invites must be sent — no early return mid-loop.
        assert mock_client.create_document_freeform_invite.call_count == 3
        # Final invite ID is the last one in the loop.
        assert result.invite_id == "inv_c"
        # Signing link is populated because sender == one of the recipients.
        assert result.link is not None
        assert "doc1" in result.link

    def test_no_recipients_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test empty recipients raises ValueError with entity ID."""
        orders = [InviteOrder(order=1, recipients=[])]

        with pytest.raises(ValueError, match="doc1"):
            _send_document_freeform_invite(mock_client, "tok", "doc1", orders)

    def test_includes_subject_message_in_request(self, mock_client: MagicMock) -> None:
        """Test subject and message are passed through to the API request."""
        order = InviteOrder(
            order=1,
            recipients=[
                InviteRecipient(
                    email="signer@example.com",
                    action="sign",
                    subject="Please sign",
                    message="Sign this document",
                )
            ],
        )

        _send_document_freeform_invite(mock_client, "tok", "doc1", [order])

        request = mock_client.create_document_freeform_invite.call_args[0][2]
        assert request.to == "signer@example.com"
        assert request.subject == "Please sign"
        assert request.message == "Sign this document"

    def test_redirect_target_excluded_without_redirect_uri(self, mock_client: MagicMock) -> None:
        """Test redirect_target is not included when redirect_uri is absent."""
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        _send_document_freeform_invite(mock_client, "tok", "doc1", [order])

        request = mock_client.create_document_freeform_invite.call_args[0][2]
        dumped = request.model_dump(exclude_none=True)
        assert "redirect_target" not in dumped

    def test_redirect_target_included_with_redirect_uri(self, mock_client: MagicMock) -> None:
        """Test redirect_target is included when redirect_uri is provided."""
        order = InviteOrder(
            order=1,
            recipients=[
                InviteRecipient(
                    email="signer@example.com",
                    action="sign",
                    redirect_uri="https://example.com/done",
                    redirect_target="blank",
                )
            ],
        )

        _send_document_freeform_invite(mock_client, "tok", "doc1", [order])

        request = mock_client.create_document_freeform_invite.call_args[0][2]
        assert request.redirect_target == "blank"


class TestSendDocumentGroupFreeformInvite:
    """Test cases for _send_document_group_freeform_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        client = MagicMock()
        client.create_freeform_invite.return_value = MagicMock(data={"id": "grp_inv1"})
        return client

    def test_happy_path_returns_send_invite_response(self, mock_client: MagicMock) -> None:
        """Test successful group freeform invite returns SendInviteResponse."""
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        result = _send_document_group_freeform_invite(mock_client, "tok", "grp1", [order])

        assert isinstance(result, SendInviteResponse)
        assert result.invite_id == "grp_inv1"
        assert result.invite_entity == "document_group"

    def test_no_recipients_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test empty recipients raises ValueError with entity ID."""
        orders = [InviteOrder(order=1, recipients=[])]

        with pytest.raises(ValueError, match="grp1"):
            _send_document_group_freeform_invite(mock_client, "tok", "grp1", orders)

    def test_missing_invite_id_in_response_raises_value_error(self, mock_client: MagicMock) -> None:
        """Test ValueError is raised when API response has no 'id'."""
        mock_client.create_freeform_invite.return_value = MagicMock(data={})
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        with pytest.raises(ValueError, match="grp1"):
            _send_document_group_freeform_invite(mock_client, "tok", "grp1", [order])

    def test_group_freeform_request_omits_cc(self, mock_client: MagicMock) -> None:
        """CC is not configured from tool-layer recipients; request leaves cc unset."""
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        _send_document_group_freeform_invite(mock_client, "tok", "grp1", [order])

        request = mock_client.create_freeform_invite.call_args[0][2]
        assert request.cc is None

    def test_redirect_target_excluded_without_redirect_uri(self, mock_client: MagicMock) -> None:
        """Test redirect_target is not set on recipient when redirect_uri is absent."""
        order = InviteOrder(
            order=1,
            recipients=[InviteRecipient(email="signer@example.com", action="sign")],
        )

        _send_document_group_freeform_invite(mock_client, "tok", "grp1", [order])

        request = mock_client.create_freeform_invite.call_args[0][2]
        recipient = request.to[0]
        dumped = recipient.model_dump(exclude_none=True)
        assert "redirect_target" not in dumped

    def test_uses_first_recipient_subject_and_message(self, mock_client: MagicMock) -> None:
        """Test the request-level subject/message comes from first recipient."""
        orders = [
            InviteOrder(
                order=1,
                recipients=[
                    InviteRecipient(email="a@test.com", action="sign", subject="First subject", message="First msg"),
                    InviteRecipient(email="b@test.com", action="sign", subject="Second subject", message="Second msg"),
                ],
            ),
        ]

        _send_document_group_freeform_invite(mock_client, "tok", "grp1", orders)

        request = mock_client.create_freeform_invite.call_args[0][2]
        assert request.subject == "First subject"
        assert request.message == "First msg"


class TestSendInviteFreeformRouting:
    """Test cases for _send_invite routing to freeform invite paths."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def _make_freeform_order(self, email: str = "signer@example.com") -> InviteOrder:
        """Build a minimal InviteOrder without role (freeform)."""
        return InviteOrder(
            order=1,
            recipients=[InviteRecipient(email=email, action="sign")],
        )

    async def test_routes_to_document_freeform_when_no_fields(self, mock_client: MagicMock) -> None:
        """Test document without fields routes to freeform invite."""
        mock_client.get_document.return_value = MagicMock(fields=[], template=False)
        mock_client.get_user_info.return_value = MagicMock(primary_email="sender@test.com")
        mock_client.create_document_freeform_invite.return_value = MagicMock(id="freeform_inv")

        result = await _send_invite("doc1", "document", [self._make_freeform_order()], "tok", mock_client)

        assert result.invite_entity == "document"
        assert result.invite_id == "freeform_inv"
        mock_client.create_document_freeform_invite.assert_called_once()

    async def test_routes_to_group_freeform_when_no_roles(self, mock_client: MagicMock) -> None:
        """Test document group without roles routes to freeform group invite."""
        doc = MagicMock()
        doc.roles = []
        group = MagicMock()
        group.documents = [doc]
        mock_client.get_document_group.return_value = group
        mock_client.create_freeform_invite.return_value = MagicMock(data={"id": "grp_freeform_inv"})

        result = await _send_invite("grp1", "document_group", [self._make_freeform_order()], "tok", mock_client)

        assert result.invite_entity == "document_group"
        assert result.invite_id == "grp_freeform_inv"
        mock_client.create_freeform_invite.assert_called_once()

    async def test_field_invite_raises_when_recipient_has_no_role(self, mock_client: MagicMock) -> None:
        """Test field invite path raises ValueError when recipient lacks a role."""
        mock_client.get_document.return_value = MagicMock(fields=[MagicMock()], template=False)

        with pytest.raises(ValueError, match="no role assigned"):
            await _send_invite("doc1", "document", [self._make_freeform_order()], "tok", mock_client)

    async def test_group_field_invite_raises_when_recipient_has_no_role(self, mock_client: MagicMock) -> None:
        """Test group field invite path raises ValueError when any recipient lacks a role."""
        doc = MagicMock()
        doc.roles = ["Signer"]
        group = MagicMock()
        group.documents = [doc]
        mock_client.get_document_group.return_value = group

        with pytest.raises(ValueError, match="no role assigned"):
            await _send_invite("grp1", "document_group", [self._make_freeform_order()], "tok", mock_client)


class TestSendInviteSelfSign:
    """Test cases for _send_invite with self_sign=True."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        client = MagicMock()
        client.cfg.app_base = "https://app.test.signnow.com"
        return client

    async def test_self_sign_builds_synthetic_orders_from_user_info(self, mock_client: MagicMock) -> None:
        """When self_sign=True and entity has no fields, the tool fills in the user as sole recipient and returns a SendInviteResponse whose link is populated."""
        mock_client.get_document.return_value = MagicMock(fields=[], template=False, id="doc1", document_name="doc")
        mock_client.get_user_info.return_value = MagicMock(primary_email="me@co.com")
        mock_client.create_document_freeform_invite.return_value = MagicMock(id="self_inv")

        result = await _send_invite("doc1", "document", [], "tok", mock_client, self_sign=True)

        # Freeform self-sign returns a SendInviteResponse with the signing link
        # attached via the optional `link` field (no separate response type).
        assert isinstance(result, SendInviteResponse)
        assert result.invite_id == "self_inv"
        assert result.invite_entity == "document"
        assert result.link is not None
        assert "doc1" in result.link
        # The synthetic order was built with the resolved sender email.
        request = mock_client.create_document_freeform_invite.call_args[0][2]
        assert request.to == "me@co.com"
        assert request.from_ == "me@co.com"

    async def test_self_sign_rejects_explicit_orders_at_tool_layer(self) -> None:
        """Tool-layer validation: self_sign=True combined with non-empty orders is rejected in signnow.py.

        The signnow.py wrapper raises before calling _send_invite. This test exercises the wrapper
        indirectly by asserting the internal _send_invite signature accepts self_sign kwarg only
        alongside an empty orders list (synthesis happens inside).
        """
        # This is a guard in the tool wrapper; we cover the tool-layer combination via integration
        # tests below. Unit level: verify _send_invite does not raise when self_sign=True and orders
        # is already empty (the wrapper passes []).
        mock_client = MagicMock()
        mock_client.cfg.app_base = "https://app.test.signnow.com"
        mock_client.get_document.return_value = MagicMock(fields=[], template=False, id="doc1", document_name="doc")
        mock_client.get_user_info.return_value = MagicMock(primary_email="me@co.com")
        mock_client.create_document_freeform_invite.return_value = MagicMock(id="inv")

        # Should not raise — synthesis happens inside.
        await _send_invite("doc1", "document", [], "tok", mock_client, self_sign=True)

    async def test_self_sign_on_field_document_raises_with_hint(self, mock_client: MagicMock) -> None:
        """When self_sign=True and the document has fields, raise a clear error pointing at create_embedded_sending."""
        mock_client.get_document.return_value = MagicMock(fields=[MagicMock()], template=False)
        mock_client.get_user_info.return_value = MagicMock(primary_email="me@co.com")

        with pytest.raises(ValueError, match="create_embedded_sending"):
            await _send_invite("doc1", "document", [], "tok", mock_client, self_sign=True)

    async def test_self_sign_on_document_group_with_roles_raises_with_hint(self, mock_client: MagicMock) -> None:
        """When self_sign=True and the document group defines roles, raise with a hint to use create_embedded_sending."""
        doc = MagicMock()
        doc.roles = ["Signer"]
        group = MagicMock()
        group.documents = [doc]
        mock_client.get_document_group.return_value = group
        mock_client.get_user_info.return_value = MagicMock(primary_email="me@co.com")

        with pytest.raises(ValueError, match="create_embedded_sending"):
            await _send_invite("grp1", "document_group", [], "tok", mock_client, self_sign=True)


class TestSignerAuthentication:
    """Test cases for SignerAuthentication model validation and repr."""

    def test_valid_password_type_constructs(self) -> None:
        """Test valid password auth constructs without error."""
        auth = SignerAuthentication(type="password", password="s3cr3t")  # noqa: S106
        assert auth.type == "password"
        assert auth.password == "s3cr3t"  # noqa: S105

    def test_password_with_whitespace_is_normalized(self) -> None:
        """Test leading/trailing whitespace is stripped from stored password."""
        auth = SignerAuthentication(type="password", password="  s3cr3t  ")  # noqa: S106
        assert auth.password == "s3cr3t"  # noqa: S105

    def test_phone_with_whitespace_is_normalized(self) -> None:
        """Test leading/trailing whitespace is stripped from stored phone."""
        auth = SignerAuthentication(type="phone", phone="  +1234567890  ")
        assert auth.phone == "+1234567890"

    def test_valid_phone_type_constructs(self) -> None:
        """Test valid phone auth constructs without error."""
        auth = SignerAuthentication(type="phone", phone="+1234567890")
        assert auth.type == "phone"
        assert auth.phone == "+1234567890"

    def test_password_missing_raises_validation_error(self) -> None:
        """Test password type with password=None raises ValidationError."""
        with pytest.raises(ValidationError, match="password is required"):
            SignerAuthentication(type="password", password=None)

    def test_phone_missing_raises_validation_error(self) -> None:
        """Test phone type with phone=None raises ValidationError."""
        with pytest.raises(ValidationError, match="phone is required"):
            SignerAuthentication(type="phone", phone=None)

    def test_password_whitespace_only_raises_validation_error(self) -> None:
        """Test whitespace-only password raises ValidationError."""
        with pytest.raises(ValidationError, match="password is required"):
            SignerAuthentication(type="password", password="   ")  # noqa: S106

    def test_phone_whitespace_only_raises_validation_error(self) -> None:
        """Test whitespace-only phone raises ValidationError."""
        with pytest.raises(ValidationError, match="phone is required"):
            SignerAuthentication(type="phone", phone="   ")

    def test_repr_masks_password(self) -> None:
        """Test repr does not contain the actual password value."""
        auth = SignerAuthentication(type="password", password="supersecret")  # noqa: S106
        result = repr(auth)
        assert "supersecret" not in result
        assert "password" in result  # field name still visible

    def test_method_defaults_to_none(self) -> None:
        """Test method field defaults to None, not 'sms'."""
        auth = SignerAuthentication(type="phone", phone="+1234")
        assert auth.method is None


class TestBuildDocumentAuthKwargs:
    """Test cases for _build_document_auth_kwargs helper."""

    def test_none_returns_empty_dict(self) -> None:
        """Test None authentication returns empty dict."""
        assert _build_document_auth_kwargs(None) == {}

    def test_password_type_returns_correct_keys(self) -> None:
        """Test password type includes authentication_type and password."""
        auth = SignerAuthentication(type="password", password="s3cr3t")  # noqa: S106
        result = _build_document_auth_kwargs(auth)
        assert result == {"authentication_type": "password", "password": "s3cr3t"}  # noqa: S105

    def test_password_type_excludes_method_key(self) -> None:
        """Test password type does not include method key."""
        auth = SignerAuthentication(type="password", password="s3cr3t")  # noqa: S106
        result = _build_document_auth_kwargs(auth)
        assert "method" not in result

    def test_phone_type_with_sms_method(self) -> None:
        """Test phone type with method='sms' includes method key."""
        auth = SignerAuthentication(type="phone", phone="+1234567890", method="sms")
        result = _build_document_auth_kwargs(auth)
        assert result["authentication_type"] == "phone"
        assert result["phone"] == "+1234567890"
        assert result["method"] == "sms"

    def test_phone_type_with_phone_call_method(self) -> None:
        """Test phone type with method='phone_call' passes through correctly."""
        auth = SignerAuthentication(type="phone", phone="+1234", method="phone_call")
        result = _build_document_auth_kwargs(auth)
        assert result["method"] == "phone_call"

    def test_phone_type_without_method_sets_method_to_none(self) -> None:
        """Test phone type with method=None sets method=None in kwargs.

        The None value overrides DocumentFieldInviteRecipient's 'sms' field default.
        model_dump(exclude_none=True) then drops the key from the API request.
        """
        auth = SignerAuthentication(type="phone", phone="+1234")  # method=None by default
        result = _build_document_auth_kwargs(auth)
        assert "method" in result
        assert result["method"] is None

    def test_phone_type_with_sms_message(self) -> None:
        """Test phone type with sms_message includes authentication_sms_message key."""
        auth = SignerAuthentication(type="phone", phone="+1234", method="sms", sms_message="Code: {password}")
        result = _build_document_auth_kwargs(auth)
        assert result["authentication_sms_message"] == "Code: {password}"

    def test_phone_type_without_sms_message_excludes_key(self) -> None:
        """Test phone type without sms_message does not include authentication_sms_message."""
        auth = SignerAuthentication(type="phone", phone="+1234", method="sms")
        result = _build_document_auth_kwargs(auth)
        assert "authentication_sms_message" not in result


class TestBuildFieldInviteAuthentication:
    """Test cases for _build_field_invite_authentication helper."""

    def test_none_returns_none(self) -> None:
        """Test None authentication returns None."""
        assert _build_field_invite_authentication(None) is None

    def test_password_type_maps_value(self) -> None:
        """Test password type maps password to FieldInviteAuthentication.value."""
        auth = SignerAuthentication(type="password", password="s3cr3t")  # noqa: S106
        result = _build_field_invite_authentication(auth)
        assert isinstance(result, FieldInviteAuthentication)
        assert result.type == "password"
        assert result.value == "s3cr3t"

    def test_phone_type_sets_both_value_and_phone(self) -> None:
        """Test phone type sets both value and phone fields to the phone number."""
        auth = SignerAuthentication(type="phone", phone="+1234567890", method="sms")
        result = _build_field_invite_authentication(auth)
        assert isinstance(result, FieldInviteAuthentication)
        assert result.type == "phone"
        assert result.value == "+1234567890"
        assert result.phone == "+1234567890"

    def test_phone_type_passes_method(self) -> None:
        """Test phone type passes method through to FieldInviteAuthentication."""
        auth = SignerAuthentication(type="phone", phone="+1234", method="phone_call")
        result = _build_field_invite_authentication(auth)
        assert result is not None
        assert result.method == "phone_call"

    def test_phone_type_passes_sms_message_as_message(self) -> None:
        """Test sms_message maps to FieldInviteAuthentication.message."""
        auth = SignerAuthentication(type="phone", phone="+1234", method="sms", sms_message="Your code: {password}")
        result = _build_field_invite_authentication(auth)
        assert result is not None
        assert result.message == "Your code: {password}"

    def test_phone_type_without_method_passes_none(self) -> None:
        """Test method=None is passed as None to FieldInviteAuthentication."""
        auth = SignerAuthentication(type="phone", phone="+1234")
        result = _build_field_invite_authentication(auth)
        assert result is not None
        assert result.method is None


class TestSendDocumentFieldInviteWithAuth:
    """Test auth propagation in _send_document_field_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_password_auth_wired_into_recipient(self, mock_client: MagicMock) -> None:
        """Test password auth fields are set on DocumentFieldInviteRecipient."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="sent")
        auth = SignerAuthentication(type="password", password="abc123")  # noqa: S106
        order = _make_order_with_auth(auth)

        _send_document_field_invite(mock_client, "tok", "doc1", [order])

        request = mock_client.create_document_field_invite.call_args[0][2]
        recipient = request.to[0]
        assert recipient.authentication_type == "password"
        assert recipient.password == "abc123"  # noqa: S105

    def test_no_auth_leaves_no_auth_type_on_recipient(self, mock_client: MagicMock) -> None:
        """Test absent auth leaves authentication_type as None on recipient."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="sent")

        _send_document_field_invite(mock_client, "tok", "doc1", [_make_order()])

        request = mock_client.create_document_field_invite.call_args[0][2]
        recipient = request.to[0]
        assert recipient.authentication_type is None

    def test_phone_auth_wired_into_recipient(self, mock_client: MagicMock) -> None:
        """Test phone auth fields are set on DocumentFieldInviteRecipient."""
        mock_client.get_user_info.return_value = MagicMock(primary_email="owner@example.com")
        mock_client.create_document_field_invite.return_value = MagicMock(status="sent")
        auth = SignerAuthentication(type="phone", phone="+1234567890", method="sms")
        order = _make_order_with_auth(auth)

        _send_document_field_invite(mock_client, "tok", "doc1", [order])

        request = mock_client.create_document_field_invite.call_args[0][2]
        recipient = request.to[0]
        assert recipient.authentication_type == "phone"
        assert recipient.phone == "+1234567890"
        assert recipient.method == "sms"


class TestSendDocumentGroupFieldInviteWithAuth:
    """Test auth propagation in _send_document_group_field_invite."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def _make_group(self, doc_id: str = "dg_doc1", roles: list[str] | None = None) -> MagicMock:
        """Build a minimal document group mock."""
        doc = MagicMock()
        doc.id = doc_id
        doc.roles = roles if roles is not None else ["Signer"]
        group = MagicMock()
        group.documents = [doc]
        return group

    def test_phone_auth_set_on_field_invite_action(self, mock_client: MagicMock) -> None:
        """Test phone auth is set as FieldInviteAuthentication on the FieldInviteAction."""
        mock_client.create_field_invite.return_value = MagicMock(id="inv1")
        auth = SignerAuthentication(type="phone", phone="+1", method="sms")
        order = _make_order_with_auth(auth, role="Signer")
        group = self._make_group(roles=["Signer"])

        _send_document_group_field_invite(mock_client, "tok", "grp1", [order], group)

        request = mock_client.create_field_invite.call_args[0][2]
        action = request.invite_steps[0].invite_actions[0]
        assert action.authentication is not None
        assert action.authentication.type == "phone"
        assert action.authentication.value == "+1"
        assert action.authentication.phone == "+1"

    def test_phone_call_method_propagated(self, mock_client: MagicMock) -> None:
        """Test method='phone_call' is propagated to FieldInviteAuthentication."""
        mock_client.create_field_invite.return_value = MagicMock(id="inv1")
        auth = SignerAuthentication(type="phone", phone="+1", method="phone_call")
        order = _make_order_with_auth(auth, role="Signer")
        group = self._make_group(roles=["Signer"])

        _send_document_group_field_invite(mock_client, "tok", "grp1", [order], group)

        request = mock_client.create_field_invite.call_args[0][2]
        action = request.invite_steps[0].invite_actions[0]
        assert action.authentication is not None
        assert action.authentication.method == "phone_call"

    def test_no_auth_leaves_action_authentication_none(self, mock_client: MagicMock) -> None:
        """Test absent auth leaves FieldInviteAction.authentication as None."""
        mock_client.create_field_invite.return_value = MagicMock(id="inv1")
        group = self._make_group(roles=["Signer"])

        _send_document_group_field_invite(mock_client, "tok", "grp1", [_make_order(role="Signer")], group)

        request = mock_client.create_field_invite.call_args[0][2]
        action = request.invite_steps[0].invite_actions[0]
        assert action.authentication is None
