"""Unit tests for embedded_sending module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.embedded_sending import (
    _create_document_embedded_sending,
    _create_document_group_embedded_sending,
    _create_embedded_sending,
)
from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse


class TestCreateDocumentEmbeddedSending:
    """Test cases for _create_document_embedded_sending."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_happy_path_returns_sending_response(self, mock_client: MagicMock) -> None:
        """Successful call returns CreateEmbeddedSendingResponse with sending_entity=document."""
        mock_client.create_document_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/doc1")
        )

        result = _create_document_embedded_sending(mock_client, "tok", "doc1", None, None, None, "manage")

        assert isinstance(result, CreateEmbeddedSendingResponse)
        assert result.sending_entity == "document"
        assert result.sending_url == "https://app.signnow.com/send/doc1"
        mock_client.create_document_embedded_sending.assert_called_once()

    def test_maps_send_invite_type_to_invite(self, mock_client: MagicMock) -> None:
        """sending_type='send-invite' maps to type='invite' in the API request payload."""
        mock_client.create_document_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/inv1")
        )

        result = _create_document_embedded_sending(mock_client, "tok", "doc1", None, None, None, "send-invite")

        call_args = mock_client.create_document_embedded_sending.call_args
        request_data = call_args.args[2]
        assert request_data.type == "invite"
        assert result.sending_entity == "document"
        assert result.sending_url == "https://app.signnow.com/send/inv1"


class TestCreateDocumentGroupEmbeddedSending:
    """Test cases for _create_document_group_embedded_sending."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    def test_happy_path_returns_sending_response(self, mock_client: MagicMock) -> None:
        """Successful call returns CreateEmbeddedSendingResponse with sending_entity=document_group."""
        mock_client.create_document_group_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/grp1")
        )

        result = _create_document_group_embedded_sending(mock_client, "tok", "grp1", None, None, None, None)

        assert isinstance(result, CreateEmbeddedSendingResponse)
        assert result.sending_entity == "document_group"
        assert result.sending_url == "https://app.signnow.com/send/grp1"
        mock_client.create_document_group_embedded_sending.assert_called_once()


class TestCreateEmbeddedSending:
    """Test cases for the merged _create_embedded_sending."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        return MagicMock()

    async def test_routes_to_document_group_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Explicit entity_type=document_group dispatches to group path; created_entity_* are None."""
        mock_client.create_document_group_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/grp")
        )

        result = await _create_embedded_sending("grp1", "document_group", None, None, None, "manage", "tok", mock_client)

        assert result.sending_entity == "document_group"
        assert result.sending_url == "https://app.signnow.com/send/grp"
        assert result.created_entity_id is None
        assert result.created_entity_type is None
        assert result.created_entity_name is None
        mock_client.create_document_group_embedded_sending.assert_called_once()

    async def test_routes_to_document_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Explicit entity_type=document dispatches to document path; created_entity_* are None."""
        mock_client.create_document_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/doc")
        )

        result = await _create_embedded_sending("doc1", "document", None, None, None, "manage", "tok", mock_client)

        assert result.sending_entity == "document"
        assert result.sending_url == "https://app.signnow.com/send/doc"
        assert result.created_entity_id is None
        assert result.created_entity_type is None
        assert result.created_entity_name is None
        mock_client.create_document_embedded_sending.assert_called_once()

    async def test_auto_detects_document_group(self, mock_client: MagicMock) -> None:
        """entity_type=None auto-detects document_group when get_document_group succeeds."""
        mock_client.get_document_group.return_value = MagicMock()
        mock_client.create_document_group_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/auto_grp")
        )

        result = await _create_embedded_sending("grp1", None, None, None, None, "manage", "tok", mock_client)

        assert result.sending_entity == "document_group"
        assert result.sending_url == "https://app.signnow.com/send/auto_grp"
        
    async def test_auto_detects_document_when_group_not_found(self, mock_client: MagicMock) -> None:
        """entity_type=None falls back to document when group and template_group both 404."""
        mock_client.get_document_group.side_effect = SignNowAPINotFoundError()
        mock_client.get_document_group_template.side_effect = SignNowAPINotFoundError()
        mock_client.get_document.return_value = MagicMock()
        mock_client.create_document_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/doc_fb")
        )

        result = await _create_embedded_sending("doc1", None, None, None, None, "manage", "tok", mock_client)

        assert result.sending_entity == "document"

    async def test_template_creates_doc_then_sends(self, mock_client: MagicMock) -> None:
        """entity_type=template creates document first, then creates sending on new entity."""
        mock_client.create_document_from_template.return_value = MagicMock(id="new_doc", document_name="New Doc")
        mock_client.create_document_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/tmpl_doc")
        )

        result = await _create_embedded_sending(
            "tmpl1", "template", None, None, None, "manage", "tok", mock_client, name="New Doc"
        )

        assert result.sending_entity == "document"
        assert result.created_entity_id == "new_doc"
        assert result.created_entity_type == "document"

    async def test_template_group_creates_group_then_sends(self, mock_client: MagicMock) -> None:
        """entity_type=template_group creates document_group first, then creates sending."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.get_document_group_template.return_value = MagicMock(group_name="My Group")
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "new_grp"})
        mock_client.create_document_group_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/tg")
        )

        result = await _create_embedded_sending(
            "tg1", "template_group", None, None, None, "manage", "tok", mock_client, name="My Group"
        )

        assert result.sending_entity == "document_group"
        assert result.created_entity_type == "document_group"

    async def test_progress_reported_three_times_for_template_flow(self, mock_client: MagicMock) -> None:
        """ctx.report_progress is called 3 times for template flows: 1/3, 2/3, 3/3."""
        ctx = AsyncMock()
        mock_client.create_document_from_template.return_value = MagicMock(id="new_doc2", document_name="Doc2")
        mock_client.create_document_embedded_sending.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/send/prog")
        )

        await _create_embedded_sending("tmpl2", "template", None, None, None, "manage", "tok", mock_client, ctx=ctx)

        assert ctx.report_progress.call_count == 3
        calls = ctx.report_progress.call_args_list
        assert calls[0].kwargs == {"progress": 1, "total": 3}
        assert calls[1].kwargs == {"progress": 2, "total": 3}
        assert calls[2].kwargs == {"progress": 3, "total": 3}