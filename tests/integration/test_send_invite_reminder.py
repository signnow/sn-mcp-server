"""
Integration tests for _send_invite_reminder — tool function wired to real SignNowAPIClient.

HTTP layer is mocked via respx; no real network calls.
Tests validate the full flow: tool function → SignNowAPIClient → HTTP construction → response parsing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.models import SendReminderResponse
from sn_mcp_server.tools.reminder import _send_invite_reminder

DOC_ID = "doc1"
GRP_ID = "grp1"


class TestSendInviteReminderDocument:
    """Integration tests for _send_invite_reminder with entity_type='document'."""

    async def test_document_happy_path_reminded(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Document with 1 pending invite → signer reminded, result correctly populated."""
        # ARRANGE
        doc_fixture = load_fixture("get_document__with_pending_invite")
        email2_fixture = load_fixture("post_email2__success")

        mock_api.get(f"/document/{DOC_ID}").respond(200, json=doc_fixture)
        mock_api.post(f"/document/{DOC_ID}/email2").respond(200, json=email2_fixture)

        # ACT
        result = await _send_invite_reminder(
            client=sn_client,
            token=token,
            entity_id=DOC_ID,
            entity_type="document",
            email=None,
            subject="Reminder",
            message="Please sign",
        )

        # ASSERT
        assert isinstance(result, SendReminderResponse)
        assert result.entity_id == DOC_ID
        assert result.entity_type == "document"
        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "signer@example.com"
        assert result.skipped == []
        assert result.failed == []

    async def test_document_not_found_raises(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Document 404 → ValueError is raised (auto-detect falls through both 404s)."""
        # ARRANGE
        error_fixture = load_fixture("error__document_not_found")
        mock_api.get("/document/doc-missing").respond(404, json=error_fixture)
        # entity_type explicitly 'document' → skips group detection, hits document 404 → propagates
        # For entity_type=None we'd need the group to 404 first too — use explicit type here.

        # ACT & ASSERT — client raises SignNowAPINotFoundError (subclass of SignNowAPIError)
        with pytest.raises(SignNowAPINotFoundError):
            await _send_invite_reminder(
                client=sn_client,
                token=token,
                entity_id="doc-missing",
                entity_type="document",
                email=None,
                subject=None,
                message=None,
            )


class TestSendInviteReminderAutoDetect:
    """Integration tests for entity_type=None auto-detection."""

    async def test_auto_detects_document_group(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → group endpoint succeeds → entity_type='document_group'."""
        # ARRANGE
        grp_fixture = load_fixture("get_document_group_v2__with_pending_invite")

        mock_api.get(f"/v2/document-groups/{GRP_ID}").respond(200, json=grp_fixture)
        mock_api.post(f"/v2/document-groups/{GRP_ID}/send-email").respond(204)

        # ACT
        result = await _send_invite_reminder(
            client=sn_client,
            token=token,
            entity_id=GRP_ID,
            entity_type=None,
            email=None,
            subject=None,
            message=None,
        )

        # ASSERT
        assert result.entity_type == "document_group"
        assert result.entity_id == GRP_ID
        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "signer@example.com"

    async def test_auto_detects_document_when_group_404(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → group 404 → falls back to document → entity_type='document'."""
        # ARRANGE
        doc_fixture = load_fixture("get_document__with_pending_invite")
        email2_fixture = load_fixture("post_email2__success")
        error_fixture = load_fixture("error__document_not_found")

        mock_api.get(f"/v2/document-groups/{DOC_ID}").respond(404, json=error_fixture)
        mock_api.get(f"/document/{DOC_ID}").respond(200, json=doc_fixture)
        mock_api.post(f"/document/{DOC_ID}/email2").respond(200, json=email2_fixture)

        # ACT
        result = await _send_invite_reminder(
            client=sn_client,
            token=token,
            entity_id=DOC_ID,
            entity_type=None,
            email=None,
            subject=None,
            message=None,
        )

        # ASSERT
        assert result.entity_type == "document"
        assert len(result.recipients_reminded) == 1


class TestSendInviteReminderDocumentGroup:
    """Integration tests for _send_invite_reminder with entity_type='document_group'."""

    async def test_group_happy_path_reminded(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Document group with 1 pending invite → signer reminded via send-email."""
        # ARRANGE
        grp_fixture = load_fixture("get_document_group_v2__with_pending_invite")

        mock_api.get(f"/v2/document-groups/{GRP_ID}").respond(200, json=grp_fixture)
        mock_api.post(f"/v2/document-groups/{GRP_ID}/send-email").respond(204)

        # ACT
        result = await _send_invite_reminder(
            client=sn_client,
            token=token,
            entity_id=GRP_ID,
            entity_type="document_group",
            email=None,
            subject=None,
            message=None,
        )

        # ASSERT
        assert result.entity_type == "document_group"
        assert result.entity_id == GRP_ID
        assert len(result.recipients_reminded) == 1
        assert result.recipients_reminded[0].email == "signer@example.com"
        assert result.failed == []
