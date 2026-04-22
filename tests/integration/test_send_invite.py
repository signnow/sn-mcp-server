"""
Integration tests for send_invite tool — full stack through real SignNowAPIClient.

HTTP layer is mocked via respx; no real network calls.
Tests validate that auth settings make it into the serialised HTTP request body.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import respx

from signnow_client import SignNowAPIClient
from sn_mcp_server.tools.models import InviteOrder, InviteRecipient, SendInviteResponse, SignerAuthentication
from sn_mcp_server.tools.send_invite import _send_document_field_invite, _send_document_group_field_invite, _send_invite

DOC_ID = "doc_auth_test"
GRP_ID = "grp_auth_test"


def _make_order(
    authentication: SignerAuthentication | None = None,
    role: str = "Signer 1",
    email: str = "signer@example.com",
) -> InviteOrder:
    """Build a minimal InviteOrder, optionally with authentication."""
    return InviteOrder(
        order=1,
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


class TestSendInviteDocumentPasswordAuth:
    """Integration tests for password authentication on the document invite path."""

    async def test_password_auth_fields_in_request_body(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Password auth fields appear in the HTTP request body sent to SignNow."""
        # ARRANGE
        user_fixture = load_fixture("get_user_info__success")
        mock_api.get("/user").respond(200, json=user_fixture)
        invite_route = mock_api.post(f"/document/{DOC_ID}/invite").respond(200, json={"status": "sent"})
        auth = SignerAuthentication(type="password", password="s3cr3t")  # noqa: S106
        order = _make_order(authentication=auth)

        # ACT
        result = _send_document_field_invite(sn_client, token, DOC_ID, [order])

        # ASSERT — response
        assert result.invite_entity == "document"
        assert result.invite_id == "sent"

        # ASSERT — request body contains auth fields
        body = json.loads(invite_route.calls[0].request.content)
        recipient = body["to"][0]
        assert recipient["authentication_type"] == "password"
        assert recipient["password"] == "s3cr3t"  # noqa: S105
        assert "phone" not in recipient

    async def test_no_auth_omits_authentication_type(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Absent auth does not inject authentication_type into request body."""
        # ARRANGE
        user_fixture = load_fixture("get_user_info__success")
        mock_api.get("/user").respond(200, json=user_fixture)
        invite_route = mock_api.post(f"/document/{DOC_ID}/invite").respond(200, json={"status": "sent"})

        # ACT
        _send_document_field_invite(sn_client, token, DOC_ID, [_make_order()])

        # ASSERT
        body = json.loads(invite_route.calls[0].request.content)
        recipient = body["to"][0]
        assert "authentication_type" not in recipient

    async def test_password_auth_omits_phone_from_request_body(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Password auth does not inject phone field into request body."""
        # ARRANGE
        user_fixture = load_fixture("get_user_info__success")
        mock_api.get("/user").respond(200, json=user_fixture)
        invite_route = mock_api.post(f"/document/{DOC_ID}/invite").respond(200, json={"status": "sent"})
        auth = SignerAuthentication(type="password", password="securepass")  # noqa: S106
        order = _make_order(authentication=auth)

        # ACT
        _send_document_field_invite(sn_client, token, DOC_ID, [order])

        # ASSERT
        body = json.loads(invite_route.calls[0].request.content)
        recipient = body["to"][0]
        assert recipient["authentication_type"] == "password"
        assert "phone" not in recipient


class TestSendInviteDocumentPhoneAuth:
    """Integration tests for phone authentication on the document invite path."""

    async def test_phone_auth_with_explicit_sms_method(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Phone auth with method='sms' propagates into request body."""
        # ARRANGE
        user_fixture = load_fixture("get_user_info__success")
        mock_api.get("/user").respond(200, json=user_fixture)
        invite_route = mock_api.post(f"/document/{DOC_ID}/invite").respond(200, json={"status": "sent"})
        auth = SignerAuthentication(type="phone", phone="+1234567890", method="sms")
        order = _make_order(authentication=auth)

        # ACT
        _send_document_field_invite(sn_client, token, DOC_ID, [order])

        # ASSERT
        body = json.loads(invite_route.calls[0].request.content)
        recipient = body["to"][0]
        assert recipient["authentication_type"] == "phone"
        assert recipient["phone"] == "+1234567890"
        assert recipient["method"] == "sms"

    async def test_phone_auth_without_method_omits_method_from_request(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Phone auth without explicit method omits method key from the API request.

        method=None overrides DocumentFieldInviteRecipient's 'sms' default and is
        then excluded by model_dump(exclude_none=True), so the key is absent.
        """
        # ARRANGE
        user_fixture = load_fixture("get_user_info__success")
        mock_api.get("/user").respond(200, json=user_fixture)
        invite_route = mock_api.post(f"/document/{DOC_ID}/invite").respond(200, json={"status": "sent"})
        auth = SignerAuthentication(type="phone", phone="+1234567890")  # method=None
        order = _make_order(authentication=auth)

        # ACT
        _send_document_field_invite(sn_client, token, DOC_ID, [order])

        # ASSERT — method=None overrides model default; exclude_none drops the key
        body = json.loads(invite_route.calls[0].request.content)
        recipient = body["to"][0]
        assert recipient["authentication_type"] == "phone"
        assert "method" not in recipient  # omitted via exclude_none=True


class TestSendInviteDocumentGroupPhoneAuth:
    """Integration tests for phone authentication on the document_group invite path."""

    async def test_phone_auth_in_field_invite_action(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Phone auth is serialised as nested authentication object in invite_actions."""
        # ARRANGE
        group_fixture = load_fixture("get_document_group__with_roles")
        mock_api.get(f"/documentgroup/{GRP_ID}").respond(200, json=group_fixture)
        invite_route = mock_api.post(f"/documentgroup/{GRP_ID}/groupinvite").respond(200, json={"id": "inv_grp_1", "pending_invite_link": None})
        auth = SignerAuthentication(type="phone", phone="+1234567890", method="sms")
        order = _make_order(authentication=auth, role="Signer 1")

        # ACT
        result = _send_document_group_field_invite(
            sn_client,
            token,
            GRP_ID,
            [order],
            sn_client.get_document_group(token, GRP_ID),
        )

        # ASSERT — response
        assert result.invite_entity == "document_group"

        # ASSERT — authentication nested object present in invite_actions
        body = json.loads(invite_route.calls[0].request.content)
        action = body["invite_steps"][0]["invite_actions"][0]
        assert "authentication" in action
        assert action["authentication"]["type"] == "phone"
        assert action["authentication"]["value"] == "+1234567890"
        assert action["authentication"]["phone"] == "+1234567890"

    async def test_phone_call_method_in_field_invite_action(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """method='phone_call' is serialised into the authentication object."""
        # ARRANGE
        group_fixture = load_fixture("get_document_group__with_roles")
        mock_api.get(f"/documentgroup/{GRP_ID}").respond(200, json=group_fixture)
        invite_route = mock_api.post(f"/documentgroup/{GRP_ID}/groupinvite").respond(200, json={"id": "inv_call_1", "pending_invite_link": None})
        auth = SignerAuthentication(type="phone", phone="+1234", method="phone_call")
        order = _make_order(authentication=auth, role="Signer 1")

        # ACT
        doc_group = sn_client.get_document_group(token, GRP_ID)
        _send_document_group_field_invite(sn_client, token, GRP_ID, [order], doc_group)

        # ASSERT
        body = json.loads(invite_route.calls[0].request.content)
        action = body["invite_steps"][0]["invite_actions"][0]
        assert action["authentication"]["method"] == "phone_call"

    async def test_no_auth_omits_authentication_from_action(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Absent auth does not inject authentication key into invite_actions."""
        # ARRANGE
        group_fixture = load_fixture("get_document_group__with_roles")
        mock_api.get(f"/documentgroup/{GRP_ID}").respond(200, json=group_fixture)
        invite_route = mock_api.post(f"/documentgroup/{GRP_ID}/groupinvite").respond(200, json={"id": "inv_noauth", "pending_invite_link": None})
        order = _make_order(role="Signer 1")

        # ACT
        doc_group = sn_client.get_document_group(token, GRP_ID)
        _send_document_group_field_invite(sn_client, token, GRP_ID, [order], doc_group)

        # ASSERT
        body = json.loads(invite_route.calls[0].request.content)
        action = body["invite_steps"][0]["invite_actions"][0]
        assert "authentication" not in action


SELF_SIGN_DOC_ID = "doc1"  # matches id in get_document__with_pending_invite fixture


class TestSendInviteSelfSign:
    """Integration tests for self-signing a field-less document via send_invite(self_sign=True)."""

    async def test_self_sign_fieldless_document_returns_signing_link(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """self_sign=True on a field-less document returns a SendInviteResponse with a populated link and sender=recipient=user primary_email."""
        # ARRANGE — the document fixture has fields: [] (freeform-eligible).
        user_fixture = load_fixture("get_user_info__success")
        doc_fixture = load_fixture("get_document__with_pending_invite")
        mock_api.get("/user").respond(200, json=user_fixture)
        mock_api.get(f"/document/{SELF_SIGN_DOC_ID}").respond(200, json=doc_fixture)
        invite_route = mock_api.post(f"/document/{SELF_SIGN_DOC_ID}/invite").respond(
            200,
            json={"result": "success", "id": "self_inv_ok", "callback_url": "https://cb.example.com"},
        )

        # ACT — self_sign=True synthesises orders internally from user_info.primary_email.
        result = await _send_invite(
            SELF_SIGN_DOC_ID,
            "document",
            [],
            token,
            sn_client,
            self_sign=True,
        )

        # ASSERT — self-sign returns a SendInviteResponse with the signing link
        # surfaced via the optional `link` field (no separate response type).
        assert isinstance(result, SendInviteResponse)
        assert result.invite_id == "self_inv_ok"
        assert result.invite_entity == "document"
        assert result.link is not None
        assert SELF_SIGN_DOC_ID in result.link
        assert token in result.link  # link embeds access token

        # ASSERT — request body: to == from == primary_email from the user fixture.
        body = json.loads(invite_route.calls[0].request.content)
        assert body["to"] == "owner@example.com"
        assert body["from"] == "owner@example.com"
