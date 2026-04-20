"""Unit tests for send_invite module."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Context
from pydantic import ValidationError

from signnow_client.exceptions import SignNowAPINotFoundError
from signnow_client.models.templates_and_documents import FieldInviteAuthentication
from sn_mcp_server.tools.models import InviteOrder, InviteRecipient, SendInviteResponse, SignerAuthentication
from sn_mcp_server.tools.send_invite import (
    _build_document_auth_kwargs,
    _build_field_invite_authentication,
    _send_document_field_invite,
    _send_document_group_field_invite,
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
        """Test explicit entity_type='document' routes to document invite path."""
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
        mock_client.get_document.return_value = MagicMock(template=False)
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
