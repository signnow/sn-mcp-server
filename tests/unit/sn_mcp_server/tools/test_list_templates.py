"""
Unit tests for list_templates module.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Context

from signnow_client.models.document_groups import DocumentGroupTemplate, DocumentGroupTemplatesResponse
from signnow_client.models.folders_lite import FolderLite, GetFolderByIdResponseLite, GetFoldersResponseLite
from sn_mcp_server.tools.list_templates import _list_all_templates
from sn_mcp_server.tools.models import TemplateSummaryList


class TestListAllTemplates:
    """Test cases for _list_all_templates function."""

    @pytest.fixture
    def mock_context(self) -> AsyncMock:
        """Create a mock FastMCP context."""
        context = AsyncMock(spec=Context)
        context.report_progress = AsyncMock()
        return context

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_folders_response(self) -> GetFoldersResponseLite:
        """Create sample folders response."""
        return GetFoldersResponseLite(
            id="root_folder_id",
            created=1640995200,  # 2022-01-01
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[
                FolderLite(
                    id="folder1",
                    created=1640995200,
                    name="Folder 1",
                    user_id="user123",
                    shared=False,
                    document_count=1,
                    folder_count=0,
                    team_name=None,
                    team_id=None,
                    team_type=None,
                ),
                FolderLite(
                    id="folder2",
                    created=1640995200,
                    name="Folder 2",
                    user_id="user123",
                    shared=False,
                    document_count=0,
                    folder_count=0,
                    team_name=None,
                    team_id=None,
                    team_type=None,
                ),
            ],
            total_documents=2,
        )

    @pytest.fixture
    def sample_folder_content_response(self) -> GetFolderByIdResponseLite:
        """Create sample folder content response."""
        return GetFolderByIdResponseLite(
            id="folder1",
            created=1640995200,
            name="Folder 1",
            user_id="user123",
            parent_id="root_folder_id",
            system_folder=False,
            shared=False,
            total_documents=2,
            documents=[
                {
                    "type": "template",
                    "id": "template2",
                    "document_name": "Template 2",
                    "template": True,
                    "updated": 1640995200,
                    "roles": [{"name": "Reviewer"}],
                },
                {
                    "type": "document",
                    "id": "document2",
                    "document_name": "Document 2",
                    "template": False,
                    "updated": 1640995200,
                    "roles": [],
                },
            ],
        )

    @pytest.fixture
    def sample_template_groups_response(self) -> DocumentGroupTemplatesResponse:
        """Create sample template groups response."""
        return DocumentGroupTemplatesResponse(
            document_group_templates=[
                DocumentGroupTemplate(
                    template_group_id="tg1",
                    template_group_name="Template Group 1",
                    folder_id="folder1",
                    last_updated=1640995200,
                    owner_email="owner@example.com",
                    templates=[
                        {"id": "t1", "name": "Template 1", "roles": ["Signer"]},
                        {"id": "t2", "name": "Template 2", "roles": ["Approver"]},
                    ],
                    is_prepared=True,
                ),
                DocumentGroupTemplate(
                    template_group_id="tg2",
                    template_group_name="Template Group 2",
                    folder_id="folder2",
                    last_updated=1640995200,
                    owner_email="owner@example.com",
                    templates=[
                        {"id": "t3", "name": "Template 3", "roles": ["Reviewer"]},
                    ],
                    is_prepared=False,
                ),
            ],
            document_group_template_total_count=2,
        )

    @pytest.mark.asyncio
    async def test_list_all_templates_success(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_response: GetFolderByIdResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test successful listing of all templates."""
        # Setup mocks
        mock_client.get_folders.return_value = sample_folders_response
        mock_client.get_folder_by_id.return_value = sample_folder_content_response
        mock_client.get_document_template_groups.return_value = sample_template_groups_response

        # Call the function
        result = await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify the result
        assert isinstance(result, TemplateSummaryList)
        assert result.total_count == 5  # 3 individual templates + 2 template groups
        assert result.offset == 0
        assert result.limit == 50
        assert result.has_more is False

        # Check individual templates from root folder
        # mock returns sample_folder_content_response for all get_folder_by_id calls,
        # which contains template2; TemplateItemLite has no roles field so roles=[]
        root_templates = [t for t in result.templates if t.entity_type == "template" and t.folder_id == "root_folder_id"]
        assert len(root_templates) == 1
        assert root_templates[0].id == "template2"
        assert root_templates[0].name == "Template 2"
        assert root_templates[0].roles == []
        assert root_templates[0].is_prepared is True

        # Check individual templates from subfolders
        subfolder_templates = [t for t in result.templates if t.entity_type == "template" and t.folder_id in ["folder1", "folder2"]]
        assert len(subfolder_templates) == 2
        # Check that we have template2 from folder1
        template2 = next((t for t in subfolder_templates if t.id == "template2"), None)
        assert template2 is not None
        assert template2.name == "Template 2"
        assert template2.roles == []  # TemplateItemLite doesn't carry roles

        # Check template groups
        template_groups = [t for t in result.templates if t.entity_type == "template_group"]
        assert len(template_groups) == 2
        assert template_groups[0].id == "tg1"
        assert template_groups[0].name == "Template Group 1"
        assert set(template_groups[0].roles) == {"Signer", "Approver"}
        assert template_groups[0].is_prepared is True
        assert template_groups[1].id == "tg2"
        assert template_groups[1].name == "Template Group 2"
        assert template_groups[1].roles == ["Reviewer"]
        assert template_groups[1].is_prepared is False

        # Verify progress reporting was called
        assert mock_context.report_progress.call_count == 5  # root + 2 folders + template groups

        # Verify API calls
        mock_client.get_folders.assert_called_once_with("test_token")
        mock_client.get_folder_by_id.assert_called()
        mock_client.get_document_template_groups.assert_called_once_with("test_token", limit=50)

    @pytest.mark.asyncio
    async def test_list_all_templates_empty_folders(self, mock_context: AsyncMock, mock_client: MagicMock) -> None:
        """Test listing templates when there are no folders or templates."""
        # Setup empty response
        empty_folders_response = GetFoldersResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[],
            total_documents=0,
        )

        empty_template_groups_response = DocumentGroupTemplatesResponse(
            document_group_templates=[],
            document_group_template_total_count=0,
        )

        mock_client.get_folders.return_value = empty_folders_response
        mock_client.get_document_template_groups.return_value = empty_template_groups_response

        # Call the function
        result = await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify the result
        assert isinstance(result, TemplateSummaryList)
        assert result.total_count == 0
        assert result.templates == []
        assert result.offset == 0
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_all_templates_folder_access_error(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test handling of folder access errors."""
        # Setup mocks
        mock_client.get_folders.return_value = sample_folders_response
        mock_client.get_folder_by_id.side_effect = Exception("Access denied")
        mock_client.get_document_template_groups.return_value = sample_template_groups_response

        # Call the function
        result = await _list_all_templates(mock_context, "test_token", mock_client)

        # All get_folder_by_id calls raise Exception — root + all subfolders are skipped
        assert isinstance(result, TemplateSummaryList)
        assert result.total_count == 2  # only 2 template groups survive (all folder accesses fail)
        assert result.offset == 0
        assert result.limit == 50
        assert result.has_more is False

        # All folder accesses raise Exception — no individual templates returned
        templates = [t for t in result.templates if t.entity_type == "template"]
        assert len(templates) == 0

        template_groups = [t for t in result.templates if t.entity_type == "template_group"]
        assert len(template_groups) == 2

    @pytest.mark.asyncio
    async def test_list_all_templates_missing_optional_fields(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
    ) -> None:
        """Test handling of documents with missing optional fields."""
        # Setup response with minimal data
        folders_response = GetFoldersResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[],
            total_documents=1,
        )

        root_folder_content = GetFolderByIdResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            total_documents=1,
            documents=[
                {
                    "type": "template",
                    "id": "template_minimal",
                    "template": True,
                    # Missing document_name, updated, roles
                },
            ],
        )

        empty_template_groups_response = DocumentGroupTemplatesResponse(
            document_group_templates=[],
            document_group_template_total_count=0,
        )

        mock_client.get_folders.return_value = folders_response
        mock_client.get_folder_by_id.return_value = root_folder_content
        mock_client.get_document_template_groups.return_value = empty_template_groups_response

        # Call the function
        result = await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify the result handles missing fields gracefully
        assert isinstance(result, TemplateSummaryList)
        assert result.total_count == 1
        assert result.offset == 0
        assert result.limit == 50
        assert result.has_more is False

        template = result.templates[0]
        assert template.id == "template_minimal"
        assert template.name == ""  # Default empty string
        assert template.roles == []  # Default empty list
        assert template.last_updated == 0  # Default 0
        assert template.is_prepared is True  # Default True

    @pytest.mark.asyncio
    async def test_list_all_templates_progress_reporting(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test that progress is reported correctly."""
        # Setup mocks
        mock_client.get_folders.return_value = sample_folders_response
        mock_client.get_document_template_groups.return_value = sample_template_groups_response

        # Call the function
        await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify progress reporting calls

        # Check that progress was reported
        assert mock_context.report_progress.call_count == 5

        # Verify the calls (we can't easily check the exact calls due to f-string formatting)
        calls = mock_context.report_progress.call_args_list
        assert calls[0][1]["progress"] == 0
        assert calls[0][1]["message"] == "Selecting all folders"
        assert calls[1][1]["progress"] == 1
        assert calls[1][1]["total"] == 4  # 2 folders + 2 (root + template groups)
        assert calls[1][1]["message"] == "Processing root folder"
        assert calls[4][1]["progress"] == 4
        assert calls[4][1]["total"] == 4
        assert calls[4][1]["message"] == "Processing template groups"


class TestListAllTemplatesPagination:
    """Test cases for _list_all_templates pagination behavior."""

    @pytest.fixture
    def mock_context(self) -> AsyncMock:
        """Create a mock FastMCP context."""
        context = AsyncMock(spec=Context)
        context.report_progress = AsyncMock()
        return context

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock SignNowAPIClient."""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_folders_response(self) -> GetFoldersResponseLite:
        """Create sample folders response."""
        return GetFoldersResponseLite(
            id="root_folder_id",
            created=1640995200,
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[
                FolderLite(
                    id="folder1",
                    created=1640995200,
                    name="Folder 1",
                    user_id="user123",
                    shared=False,
                    document_count=1,
                    folder_count=0,
                    team_name=None,
                    team_id=None,
                    team_type=None,
                ),
                FolderLite(
                    id="folder2",
                    created=1640995200,
                    name="Folder 2",
                    user_id="user123",
                    shared=False,
                    document_count=0,
                    folder_count=0,
                    team_name=None,
                    team_id=None,
                    team_type=None,
                ),
            ],
            total_documents=2,
        )

    @pytest.fixture
    def sample_folder_content_response(self) -> GetFolderByIdResponseLite:
        """Create sample folder content response with a template."""
        return GetFolderByIdResponseLite(
            id="folder1",
            created=1640995200,
            name="Folder 1",
            user_id="user123",
            parent_id="root_folder_id",
            system_folder=False,
            shared=False,
            total_documents=1,
            documents=[
                {
                    "type": "template",
                    "id": "template1",
                    "document_name": "Template 1",
                    "template": True,
                    "updated": 1640995200,
                    "roles": [{"name": "Signer"}],
                },
            ],
        )

    @pytest.fixture
    def sample_template_groups_response(self) -> DocumentGroupTemplatesResponse:
        """Create sample template groups response with 2 groups."""
        return DocumentGroupTemplatesResponse(
            document_group_templates=[
                DocumentGroupTemplate(
                    template_group_id="tg1",
                    template_group_name="Template Group 1",
                    folder_id="folder1",
                    last_updated=1640995200,
                    owner_email="owner@example.com",
                    templates=[{"id": "t1", "name": "Template 1", "roles": ["Signer"]}],
                    is_prepared=True,
                ),
                DocumentGroupTemplate(
                    template_group_id="tg2",
                    template_group_name="Template Group 2",
                    folder_id="folder2",
                    last_updated=1640995200,
                    owner_email="owner@example.com",
                    templates=[{"id": "t2", "name": "Template 2", "roles": ["Reviewer"]}],
                    is_prepared=False,
                ),
            ],
            document_group_template_total_count=2,
        )

    def _setup_mocks(
        self,
        mock_client: MagicMock,
        folders: GetFoldersResponseLite,
        folder_content: GetFolderByIdResponseLite,
        template_groups: DocumentGroupTemplatesResponse,
    ) -> None:
        """Configure mock client with standard responses."""
        mock_client.get_folders.return_value = folders
        mock_client.get_folder_by_id.return_value = folder_content
        mock_client.get_document_template_groups.return_value = template_groups

    @pytest.mark.asyncio
    async def test_list_templates_with_limit(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_response: GetFolderByIdResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test that limit restricts the number of returned items."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_response, sample_template_groups_response)

        # 3 folders produce 3 templates from folder_content + 2 template groups = 5 total
        result = await _list_all_templates(mock_context, "test_token", mock_client, limit=2)

        assert result.total_count == 5
        assert len(result.templates) == 2
        assert result.offset == 0
        assert result.limit == 2
        assert result.has_more is True

    @pytest.mark.asyncio
    async def test_list_templates_with_offset(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_response: GetFolderByIdResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test that offset skips items correctly."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_response, sample_template_groups_response)

        result = await _list_all_templates(mock_context, "test_token", mock_client, limit=50, offset=3)

        assert result.total_count == 5
        assert len(result.templates) == 2  # items at index 3, 4
        assert result.offset == 3
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_templates_offset_beyond_total(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_response: GetFolderByIdResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test that offset beyond total returns empty list."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_response, sample_template_groups_response)

        result = await _list_all_templates(mock_context, "test_token", mock_client, limit=50, offset=100)

        assert result.total_count == 5
        assert len(result.templates) == 0
        assert result.offset == 100
        assert result.limit == 50
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_templates_limit_and_offset(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_response: GetFolderByIdResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test pagination with both limit and offset."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_response, sample_template_groups_response)

        result = await _list_all_templates(mock_context, "test_token", mock_client, limit=2, offset=1)

        assert result.total_count == 5
        assert len(result.templates) == 2  # items at index 1, 2
        assert result.offset == 1
        assert result.limit == 2
        assert result.has_more is True

    @pytest.mark.asyncio
    async def test_list_templates_exact_page_boundary(
        self,
        mock_context: AsyncMock,
        mock_client: MagicMock,
        sample_folders_response: GetFoldersResponseLite,
        sample_folder_content_response: GetFolderByIdResponseLite,
        sample_template_groups_response: DocumentGroupTemplatesResponse,
    ) -> None:
        """Test pagination at exact page boundary (offset+limit == total)."""
        self._setup_mocks(mock_client, sample_folders_response, sample_folder_content_response, sample_template_groups_response)

        result = await _list_all_templates(mock_context, "test_token", mock_client, limit=2, offset=3)

        assert result.total_count == 5
        assert len(result.templates) == 2  # items at index 3, 4
        assert result.offset == 3
        assert result.limit == 2
        assert result.has_more is False
