"""
Integration tests for _create_embedded_sending — tool function wired to real SignNowAPIClient.

HTTP layer is mocked via respx; no real network calls.
Tests validate the full flow: tool function → SignNowAPIClient → HTTP construction → response parsing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIAuthenticationError, SignNowAPINotFoundError
from sn_mcp_server.tools.embedded_sending import _create_embedded_sending
from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse

DOC_ID = "doc1"
GRP_ID = "grp1"


class TestCreateEmbeddedSendingDocumentExplicit:
    """Integration tests for _create_embedded_sending with entity_type='document'."""

    async def test_happy_path_returns_sending_response(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Explicit document → POST embedded-sending → CreateEmbeddedSendingResponse returned."""
        fixture = load_fixture("post_embedded_sending__success")
        mock_api.post(f"/v2/documents/{DOC_ID}/embedded-sending").respond(200, json=fixture)

        result = await _create_embedded_sending(
            entity_id=DOC_ID,
            entity_type="document",
            redirect_uri=None,
            redirect_target=None,
            link_expiration_minutes=None,
            sending_type="manage",
            token=token,
            client=sn_client,
        )

        assert isinstance(result, CreateEmbeddedSendingResponse)
        assert result.sending_entity == "document"
        assert result.sending_url == fixture["data"]["url"]
        assert result.created_entity_id is None
        assert result.created_entity_type is None

    async def test_not_found_propagates_error(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """404 on POST embedded-sending → SignNowAPINotFoundError propagates to caller."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post(f"/v2/documents/{DOC_ID}/embedded-sending").respond(404, json=error_fixture)

        with pytest.raises(SignNowAPINotFoundError):
            await _create_embedded_sending(
                entity_id=DOC_ID,
                entity_type="document",
                redirect_uri=None,
                redirect_target=None,
                link_expiration_minutes=None,
                sending_type="manage",
                token=token,
                client=sn_client,
            )


class TestCreateEmbeddedSendingDocumentGroupExplicit:
    """Integration tests for _create_embedded_sending with entity_type='document_group'."""

    async def test_happy_path_returns_sending_response(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """Explicit document_group → POST group embedded-sending → CreateEmbeddedSendingResponse."""
        fixture = load_fixture("post_embedded_sending_group__success")
        mock_api.post(f"/v2/document-groups/{GRP_ID}/embedded-sending").respond(200, json=fixture)

        result = await _create_embedded_sending(
            entity_id=GRP_ID,
            entity_type="document_group",
            redirect_uri=None,
            redirect_target=None,
            link_expiration_minutes=None,
            sending_type="manage",
            token=token,
            client=sn_client,
        )

        assert isinstance(result, CreateEmbeddedSendingResponse)
        assert result.sending_entity == "document_group"
        assert result.sending_url == fixture["data"]["url"]
        assert result.created_entity_id is None

    async def test_not_found_propagates_error(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """404 on POST group embedded-sending → SignNowAPINotFoundError propagates."""
        error_fixture = load_fixture("error__document_not_found")
        mock_api.post(f"/v2/document-groups/{GRP_ID}/embedded-sending").respond(404, json=error_fixture)

        with pytest.raises(SignNowAPINotFoundError):
            await _create_embedded_sending(
                entity_id=GRP_ID,
                entity_type="document_group",
                redirect_uri=None,
                redirect_target=None,
                link_expiration_minutes=None,
                sending_type="manage",
                token=token,
                client=sn_client,
            )


class TestCreateEmbeddedSendingAutoDetect:
    """Integration tests for _create_embedded_sending with entity_type=None (auto-detection)."""

    async def test_auto_detects_document_group_first(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → tries document_group first → succeeds → group sending used."""
        group_fixture = load_fixture("get_document_group__with_roles")
        sending_fixture = load_fixture("post_embedded_sending_group__success")

        group_route = mock_api.get(f"/documentgroup/{GRP_ID}").respond(200, json=group_fixture)
        mock_api.post(f"/v2/document-groups/{GRP_ID}/embedded-sending").respond(200, json=sending_fixture)

        result = await _create_embedded_sending(
            entity_id=GRP_ID,
            entity_type=None,
            redirect_uri=None,
            redirect_target=None,
            link_expiration_minutes=None,
            sending_type="manage",
            token=token,
            client=sn_client,
        )

        assert isinstance(result, CreateEmbeddedSendingResponse)
        assert result.sending_entity == "document_group"
        assert result.sending_url == sending_fixture["data"]["url"]
        assert group_route.called

    async def test_auto_detect_falls_back_to_document(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """entity_type=None → group 404 → template_group 404 → document succeeds → doc sending."""
        error_fixture = load_fixture("error__document_not_found")
        doc_fixture = load_fixture("get_document__with_pending_invite")
        sending_fixture = load_fixture("post_embedded_sending__success")

        mock_api.get(f"/documentgroup/{DOC_ID}").respond(404, json=error_fixture)
        mock_api.get(f"/documentgroup/template/{DOC_ID}").respond(404, json=error_fixture)
        mock_api.get(f"/document/{DOC_ID}").respond(200, json=doc_fixture)
        mock_api.post(f"/v2/documents/{DOC_ID}/embedded-sending").respond(200, json=sending_fixture)

        result = await _create_embedded_sending(
            entity_id=DOC_ID,
            entity_type=None,
            redirect_uri=None,
            redirect_target=None,
            link_expiration_minutes=None,
            sending_type="manage",
            token=token,
            client=sn_client,
        )

        assert isinstance(result, CreateEmbeddedSendingResponse)
        assert result.sending_entity == "document"
        assert result.sending_url == sending_fixture["data"]["url"]

    async def test_non_404_on_group_probe_propagates(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """entity_type=None → group returns 403 → SignNowAPIAuthenticationError propagates."""
        mock_api.get(f"/documentgroup/{DOC_ID}").respond(
            403,
            json={"errors": [{"code": "403", "message": "Forbidden"}]},
        )

        with pytest.raises(SignNowAPIAuthenticationError):
            await _create_embedded_sending(
                entity_id=DOC_ID,
                entity_type=None,
                redirect_uri=None,
                redirect_target=None,
                link_expiration_minutes=None,
                sending_type="manage",
                token=token,
                client=sn_client,
            )
