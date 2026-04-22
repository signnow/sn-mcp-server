"""Unit tests for the signing_link module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sn_mcp_server.tools.models import DocumentGroup, SimplifiedInvite
from sn_mcp_server.tools.signing_link import _get_signing_link


APP_BASE = "https://app.example.com"
FAKE_TOKEN = "tok"  # noqa: S105


def _make_client(app_base: str = APP_BASE) -> MagicMock:
    """Build a minimal client mock with cfg.app_base."""
    client = MagicMock()
    client.cfg.app_base = app_base
    return client


def _make_document_group(
    *,
    entity_id: str = "doc1",
    entity_type: str = "document",
    invite: SimplifiedInvite | None = None,
    freeform_invite_id: str | None = None,
) -> DocumentGroup:
    """Build a DocumentGroup with configurable invite / freeform invite state."""
    return DocumentGroup(
        last_updated=0,
        entity_id=entity_id,
        group_name="Test",
        entity_type=entity_type,
        invite=invite,
        freeform_invite_id=freeform_invite_id,
        documents=[],
    )


class TestGetSigningLinkInviteCheck:
    """Invite presence checks on the unified DocumentGroup."""

    def test_raises_when_document_has_no_invite_and_no_freeform(self) -> None:
        """Document with neither classic invite nor freeform invite → ValueError."""
        client = _make_client()
        dg = _make_document_group(entity_type="document", invite=None, freeform_invite_id=None)

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            with pytest.raises(ValueError, match="doc1"):
                _get_signing_link("doc1", "document", FAKE_TOKEN, client)

    def test_raises_when_document_group_has_no_invite_and_no_freeform(self) -> None:
        """Document group with neither classic invite nor freeform invite → ValueError."""
        client = _make_client()
        dg = _make_document_group(entity_id="grp1", entity_type="document_group", invite=None, freeform_invite_id=None)

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            with pytest.raises(ValueError, match="grp1"):
                _get_signing_link("grp1", "document_group", FAKE_TOKEN, client)

    def test_document_with_classic_invite_returns_link(self) -> None:
        """Document whose classic invite is populated produces a webapp link."""
        client = _make_client()
        invite = SimplifiedInvite(invite_id="inv1")
        dg = _make_document_group(entity_type="document", invite=invite, freeform_invite_id=None)

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            result = _get_signing_link("doc1", "document", FAKE_TOKEN, client)

        assert result.link == f"{APP_BASE}/webapp/document/doc1?access_token={FAKE_TOKEN}"

    def test_document_with_only_freeform_invite_returns_link(self) -> None:
        """Document whose only invite is freeform (requests[]) still produces a link."""
        client = _make_client()
        dg = _make_document_group(entity_type="document", invite=None, freeform_invite_id="freeform-abc")

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            result = _get_signing_link("doc1", "document", FAKE_TOKEN, client)

        assert result.link == f"{APP_BASE}/webapp/document/doc1?access_token={FAKE_TOKEN}"

    def test_document_group_with_only_freeform_invite_returns_link(self) -> None:
        """Document group whose only invite is freeform_invite still produces a link."""
        client = _make_client()
        dg = _make_document_group(entity_id="grp1", entity_type="document_group", invite=None, freeform_invite_id="freeform-xyz")

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            result = _get_signing_link("grp1", "document_group", FAKE_TOKEN, client)

        assert "document_group_id=grp1" in result.link
        assert f"access_token={FAKE_TOKEN}" in result.link
        assert result.link.endswith("&unwrap")

    def test_document_group_with_classic_invite_returns_link(self) -> None:
        """Document group with a classic invite produces the documentgroup signing URL."""
        client = _make_client()
        invite = SimplifiedInvite(invite_id="grp_inv")
        dg = _make_document_group(entity_id="grp1", entity_type="document_group", invite=invite, freeform_invite_id=None)

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            result = _get_signing_link("grp1", "document_group", FAKE_TOKEN, client)

        assert result.link.startswith(f"{APP_BASE}/webapp/documentgroup/signing?")

    def test_raises_for_non_document_entity(self) -> None:
        """Entity that is neither document nor document_group → ValueError."""
        client = _make_client()
        dg = _make_document_group(entity_id="tpl1", entity_type="template_group", invite=None, freeform_invite_id=None)

        with patch("sn_mcp_server.tools.signing_link._get_document", return_value=dg):
            with pytest.raises(ValueError, match="tpl1"):
                _get_signing_link("tpl1", None, FAKE_TOKEN, client)
