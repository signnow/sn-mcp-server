"""
Unit tests for list_documents module — pagination behavior.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Context

from signnow_client.models.folders_lite import GetFolderByIdResponseLite, GetFoldersResponseLite
from sn_mcp_server.tools.list_documents import _list_document_groups, _matches_expired_filter
from sn_mcp_server.tools.models import SimplifiedDocumentGroupsResponse, SimplifiedInvite


class TestListDocumentGroupsPagination:
    """Test cases for _list_document_groups pagination behavior."""

    @pytest.fixture
    def mock_context(self) -> AsyncMock:
        """Create a mock FastMCP context."""
        context = AsyncMock(spec=Context)
        context.report_progress = AsyncMock()
        return context

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    @pytest.fixture
    def sample_folders_response(self) -> GetFoldersResponseLite:
        """Create sample folders response with root folder only."""
        return GetFoldersResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[],
            total_documents=5,
        )

    @pytest.fixture
    def sample_folder_content_5_items(self) -> GetFolderByIdResponseLite:
        """Create sample folder content with 3 documents + 2 document groups = 5 items."""
        return GetFolderByIdResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            total_documents=5,
            documents=[
                {
                    "type": "document",
                    "id": "doc1",
                    "document_name": "Document 1",
                    "template": False,
                    "updated": 1640995200,
                    "roles": ["Signer"],
                },
                {
                    "type": "document",
                    "id": "doc2",
                    "document_name": "Document 2",
                    "template": False,
                    "updated": 1640995201,
                    "roles": ["Signer"],
                },
                {
                    "type": "document",
                    "id": "doc3",
                    "document_name": "Document 3",
                    "template": False,
                    "updated": 1640995202,
                    "roles": [],
                },
                {
                    "type": "document-group",
                    "id": "dg1",
                    "document_group_name": "Doc Group 1",
                    "updated": 1640995203,
                    "documents": [
                        {"id": "dg1_doc1", "name": "DG1 Doc 1", "roles": ["Signer"]},
                    ],
                },
                {
                    "type": "document-group",
                    "id": "dg2",
                    "document_group_name": "Doc Group 2",
                    "updated": 1640995204,
                    "documents": [
                        {"id": "dg2_doc1", "name": "DG2 Doc 1", "roles": ["Reviewer"]},
                    ],
                },
            ],
        )

    def _setup_mocks(
        self,
        mock_client: MagicMock,
        folders: GetFoldersResponseLite,
        folder_content: GetFolderByIdResponseLite,
    ) -> None:
        """Configure mock client with standard responses."""
        mock_client.get_folders.return_value = folders
        mock_client.get_folder_by_id.return_value = folder_content

    @pytest.mark.asyncio
    async def test_list_documents_default_pagination(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test default pagination returns all items when total < limit."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        result = await _list_document_groups(mock_context, "test_token", mock_client)

        assert isinstance(result, SimplifiedDocumentGroupsResponse)
        assert result.document_group_total_count == 5
        assert len(result.document_groups) == 5
        assert result.offset == 0
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_documents_with_limit(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test that limit restricts the number of returned items."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        result = await _list_document_groups(mock_context, "test_token", mock_client, limit=2)

        assert result.document_group_total_count == 5
        assert len(result.document_groups) == 2
        assert result.offset == 0
        assert result.limit == 2
        assert result.has_more is True

    @pytest.mark.asyncio
    async def test_list_documents_with_offset(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test that offset skips items correctly."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        result = await _list_document_groups(mock_context, "test_token", mock_client, limit=50, offset=3)

        assert result.document_group_total_count == 5
        assert len(result.document_groups) == 2  # items at index 3, 4
        assert result.offset == 3
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_documents_offset_beyond_total(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test that offset beyond total returns empty list."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        result = await _list_document_groups(mock_context, "test_token", mock_client, limit=50, offset=100)

        assert result.document_group_total_count == 5
        assert len(result.document_groups) == 0
        assert result.offset == 100
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_documents_limit_and_offset(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test pagination with both limit and offset."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        result = await _list_document_groups(mock_context, "test_token", mock_client, limit=2, offset=1)

        assert result.document_group_total_count == 5
        assert len(result.document_groups) == 2  # items at index 1, 2
        assert result.offset == 1
        assert result.limit == 2
        assert result.has_more is True

    @pytest.mark.asyncio
    async def test_list_documents_empty_result(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
    ) -> None:
        """Test pagination with no documents returns empty result."""
        empty_folder_content = GetFolderByIdResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            total_documents=0,
            documents=[],
        )
        self._setup_mocks(mock_client, sample_folders_response, empty_folder_content)

        result = await _list_document_groups(mock_context, "test_token", mock_client)

        assert result.document_group_total_count == 0
        assert len(result.document_groups) == 0
        assert result.offset == 0
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_documents_exact_page_boundary(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test pagination at exact page boundary (offset+limit == total)."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        result = await _list_document_groups(mock_context, "test_token", mock_client, limit=2, offset=3)

        assert result.document_group_total_count == 5
        assert len(result.document_groups) == 2  # items at index 3, 4
        assert result.offset == 3
        assert result.limit == 2
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_documents_invalid_expired_filter_raises(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test that an invalid expired_filter value raises ValueError."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        with pytest.raises(ValueError, match="expired_filter must be one of"):
            await _list_document_groups(mock_context, "test_token", mock_client, expired_filter="invalid_value")

    @pytest.mark.asyncio
    async def test_list_documents_expired_filter_affects_total_count(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
    ) -> None:
        """Test that expired_filter is applied before pagination so total_count reflects filtered items."""
        # 2 expired documents + 1 non-expired document = 3 total in folder
        folder_with_mixed_expiry = GetFolderByIdResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            total_documents=3,
            documents=[
                {
                    "type": "document",
                    "id": "expired_doc1",
                    "document_name": "Expired Doc 1",
                    "field_invites": [{"id": "fi1", "status": "expired"}],
                },
                {
                    "type": "document",
                    "id": "expired_doc2",
                    "document_name": "Expired Doc 2",
                    "field_invites": [{"id": "fi2", "status": "expired"}],
                },
                {
                    "type": "document",
                    "id": "active_doc1",
                    "document_name": "Active Doc",
                    "field_invites": [],
                },
            ],
        )
        mock_client.get_folders.return_value = sample_folders_response
        mock_client.get_folder_by_id.return_value = folder_with_mixed_expiry

        result = await _list_document_groups(mock_context, "test_token", mock_client, expired_filter="expired", limit=1)

        # Filter applied BEFORE pagination — total_count is filtered count, not raw count
        assert result.document_group_total_count == 2
        assert len(result.document_groups) == 1
        assert result.has_more is True
        assert result.limit == 1
        assert result.offset == 0

    @pytest.mark.asyncio
    async def test_list_documents_pagination_preserves_order(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_5_items: GetFolderByIdResponseLite,
    ) -> None:
        """Test that pagination preserves item order across pages."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_5_items)

        # Get first page
        page1 = await _list_document_groups(mock_context, "test_token", mock_client, limit=3, offset=0)
        # Get second page
        page2 = await _list_document_groups(mock_context, "test_token", mock_client, limit=3, offset=3)

        # Combined should have all 5 items
        all_ids = [g.id for g in page1.document_groups] + [g.id for g in page2.document_groups]
        assert len(all_ids) == 5
        assert len(set(all_ids)) == 5  # all unique


class TestMatchesExpiredFilter:
    """Test cases for _matches_expired_filter function."""

    @pytest.fixture
    def expired_invite(self) -> SimplifiedInvite:
        """Create a SimplifiedInvite with expired=True."""
        return SimplifiedInvite(expired=True)

    @pytest.fixture
    def active_invite(self) -> SimplifiedInvite:
        """Create a SimplifiedInvite with expired=False."""
        return SimplifiedInvite(expired=False)

    def test_filter_none_always_matches(self, active_invite: SimplifiedInvite) -> None:
        """Test that expired_filter=None always returns True."""
        assert _matches_expired_filter(active_invite, None) is True
        assert _matches_expired_filter(None, None) is True

    def test_filter_all_always_matches(self, expired_invite: SimplifiedInvite) -> None:
        """Test that expired_filter='all' always returns True."""
        assert _matches_expired_filter(expired_invite, "all") is True
        assert _matches_expired_filter(None, "all") is True

    def test_filter_expired_with_expired_invite(self, expired_invite: SimplifiedInvite) -> None:
        """Test that expired_filter='expired' returns True for expired invite."""
        assert _matches_expired_filter(expired_invite, "expired") is True

    def test_filter_expired_with_active_invite(self, active_invite: SimplifiedInvite) -> None:
        """Test that expired_filter='expired' returns False for non-expired invite."""
        assert _matches_expired_filter(active_invite, "expired") is False

    def test_filter_expired_with_none_invite(self) -> None:
        """Test that expired_filter='expired' returns False when invite is None."""
        assert _matches_expired_filter(None, "expired") is False

    def test_filter_not_expired_with_active_invite(self, active_invite: SimplifiedInvite) -> None:
        """Test that expired_filter='not-expired' returns True for non-expired invite."""
        assert _matches_expired_filter(active_invite, "not-expired") is True

    def test_filter_not_expired_with_expired_invite(self, expired_invite: SimplifiedInvite) -> None:
        """Test that expired_filter='not-expired' returns False for expired invite."""
        assert _matches_expired_filter(expired_invite, "not-expired") is False

    def test_filter_not_expired_with_none_invite(self) -> None:
        """Test that expired_filter='not-expired' returns True when invite is None (no expiry = not expired)."""
        assert _matches_expired_filter(None, "not-expired") is True
