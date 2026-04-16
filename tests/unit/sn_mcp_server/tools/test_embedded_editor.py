"""Unit tests for embedded_editor module."""

from unittest import result
from unittest.mock import AsyncMock, MagicMock

import pytest

from signnow_client.exceptions import SignNowAPINotFoundError
from sn_mcp_server.tools.embedded_editor import (
    _create_document_embedded_editor,
    _create_document_group_embedded_editor,
    _create_embedded_editor,
)
from sn_mcp_server.tools.models import CreateEmbeddedEditorResponse


class TestCreateDocumentEmbeddedEditor:
    """Test cases for _create_document_embedded_editor."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_happy_path_returns_editor_response(self, mock_client: MagicMock) -> None:
        """Successful call returns CreateEmbeddedEditorResponse with editor_entity=document."""
        mock_client.create_document_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/doc1")
        )

        result = _create_document_embedded_editor(mock_client, "tok", "doc1", None, None, None)

        assert isinstance(result, CreateEmbeddedEditorResponse)
        assert result.editor_entity == "document"
        assert result.editor_url == "https://app.signnow.com/editor/doc1"
        mock_client.create_document_embedded_editor.assert_called_once()

    def test_passes_redirect_uri_and_expiration(self, mock_client: MagicMock) -> None:
        """redirect_uri and link_expiration_minutes are forwarded to the API request."""
        mock_client.create_document_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/doc2")
        )

        _create_document_embedded_editor(mock_client, "tok", "doc2", "https://example.com/done", None, 30)

        call_args = mock_client.create_document_embedded_editor.call_args
        request_data = call_args.args[2]
        assert request_data.redirect_uri == "https://example.com/done"
        assert request_data.link_expiration == 30


class TestCreateDocumentGroupEmbeddedEditor:
    """Test cases for _create_document_group_embedded_editor."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_happy_path_returns_editor_response(self, mock_client: MagicMock) -> None:
        """Successful call returns CreateEmbeddedEditorResponse with editor_entity=document_group."""
        mock_client.create_document_group_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/grp1")
        )

        result = _create_document_group_embedded_editor(mock_client, "tok", "grp1", None, None, None)

        assert isinstance(result, CreateEmbeddedEditorResponse)
        assert result.editor_entity == "document_group"
        assert result.editor_url == "https://app.signnow.com/editor/grp1"
        mock_client.create_document_group_embedded_editor.assert_called_once()

    def test_passes_redirect_uri_and_expiration(self, mock_client: MagicMock) -> None:
        """redirect_uri and link_expiration_minutes are forwarded to the API request."""
        mock_client.create_document_group_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/grp2")
        )

        _create_document_group_embedded_editor(mock_client, "tok", "grp2", "https://example.com/done", None, 60)

        call_args = mock_client.create_document_group_embedded_editor.call_args
        request_data = call_args.args[2]
        assert request_data.redirect_uri == "https://example.com/done"
        assert request_data.link_expiration == 60


class TestCreateEmbeddedEditor:
    """Test cases for the merged _create_embedded_editor."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    async def test_routes_to_document_group_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Explicit entity_type=document_group dispatches to group path; created_entity_* are None."""
        mock_client.create_document_group_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/grp")
        )

        result = await _create_embedded_editor("grp1", "document_group", None, None, None, "tok", mock_client)

        assert result.editor_entity == "document_group"
        assert result.editor_url == "https://app.signnow.com/editor/grp"
        assert result.created_entity_id is None
        assert result.created_entity_type is None
        assert result.created_entity_name is None
        mock_client.create_document_group_embedded_editor.assert_called_once()

    async def test_routes_to_document_when_explicit_type(self, mock_client: MagicMock) -> None:
        """Explicit entity_type=document dispatches to document path; created_entity_* are None."""
        mock_client.create_document_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/doc")
        )

        result = await _create_embedded_editor("doc1", "document", None, None, None, "tok", mock_client)

        assert result.editor_entity == "document"
        assert result.editor_url == "https://app.signnow.com/editor/doc"
        assert result.created_entity_id is None
        assert result.created_entity_type is None
        assert result.created_entity_name is None
        mock_client.create_document_embedded_editor.assert_called_once()

    async def test_template_creates_then_edits(self, mock_client: MagicMock) -> None:
        """entity_type=template creates document first, then creates editor on new entity."""
        mock_client.create_document_from_template.return_value = MagicMock(id="new_doc", document_name="New Doc")
        mock_client.create_document_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/new_doc")
        )

        result = await _create_embedded_editor(
            "tmpl1", "template", None, None, None, "tok", mock_client, name="New Doc"
        )

        assert result.editor_url == "https://app.signnow.com/editor/new_doc"
        assert result.editor_entity == "document"
        assert result.created_entity_id == "new_doc"
        assert result.created_entity_type == "document"

    async def test_template_group_creates_then_edits(self, mock_client: MagicMock) -> None:
        """entity_type=template_group creates document_group first, then creates editor."""
        mock_client.get_document_template_groups.return_value = MagicMock(document_group_templates=[])
        mock_client.get_document_group_template.return_value = MagicMock(group_name="My Group")
        mock_client.create_document_group_from_template.return_value = MagicMock(data={"unique_id": "new_grp"})
        mock_client.create_document_group_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/tg")
        )

        result = await _create_embedded_editor(
            "tg1", "template_group", None, None, None, "tok", mock_client, name="My Group"
        )

        assert result.editor_entity == "document_group"
        assert result.editor_url == "https://app.signnow.com/editor/tg"
        assert result.created_entity_id == "new_grp"
        assert result.created_entity_type == "document_group"
        assert result.created_entity_name == "My Group"

    async def test_progress_reported_for_template_flow(self, mock_client: MagicMock) -> None:
        """ctx.report_progress is called 3 times for template flows: 1/3, 2/3, 3/3."""
        ctx = AsyncMock()
        mock_client.create_document_from_template.return_value = MagicMock(id="new_doc2", document_name="Doc2")
        mock_client.create_document_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/prog")
        )

        await _create_embedded_editor("tmpl2", "template", None, None, None, "tok", mock_client, ctx=ctx)

        assert ctx.report_progress.call_count == 3
        calls = ctx.report_progress.call_args_list
        assert calls[0].kwargs == {"progress": 1, "total": 3}
        assert calls[1].kwargs == {"progress": 2, "total": 3}
        assert calls[2].kwargs == {"progress": 3, "total": 3}

    async def test_no_progress_when_ctx_none(self, mock_client: MagicMock) -> None:
        """ctx=None on a direct document call raises no errors."""
        mock_client.create_document_embedded_editor.return_value = MagicMock(
            data=MagicMock(url="https://app.signnow.com/editor/noctx")
        )

        result = await _create_embedded_editor("doc1", "document", None, None, None, "tok", mock_client, ctx=None)

        assert result.editor_entity == "document"
