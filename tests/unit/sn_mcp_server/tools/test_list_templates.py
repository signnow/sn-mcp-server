"""
Unit tests for list_templates module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context

from sn_mcp_server.tools.list_templates import _list_all_templates
from sn_mcp_server.tools.models import TemplateSummary, TemplateSummaryList
from signnow_client.models.other_models import GetFoldersResponse, Folder, GetFolderByIdResponse
from signnow_client.models.document_groups import DocumentGroupTemplatesResponse, DocumentGroupTemplate


class TestListAllTemplates:
    """Test cases for _list_all_templates function."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP context."""
        context = AsyncMock(spec=Context)
        context.report_progress = AsyncMock()
        return context

    @pytest.fixture
    def mock_client(self):
        """Create a mock SignNowAPIClient."""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_folders_response(self):
        """Create sample folders response."""
        return GetFoldersResponse(
            id="root_folder_id",
            created="2024-01-01T00:00:00Z",
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[
                Folder(
                    id="folder1",
                    created="2024-01-01T00:00:00Z",
                    name="Folder 1",
                    user_id="user123",
                    shared=False,
                    document_count="1",
                    folder_count="0",
                    sub_folders=None,
                    team_name=None,
                    team_id=None,
                    team_type=None,
                ),
                Folder(
                    id="folder2",
                    created="2024-01-01T00:00:00Z",
                    name="Folder 2",
                    user_id="user123",
                    shared=False,
                    document_count="0",
                    folder_count="0",
                    sub_folders=None,
                    team_name=None,
                    team_id=None,
                    team_type=None,
                ),
            ],
            total_documents=2,
            documents=[
                {
                    "id": "template1",
                    "document_name": "Template 1",
                    "template": True,
                    "updated": "1640995200",  # 2022-01-01
                    "roles": [{"name": "Signer"}, {"name": "Approver"}],
                },
                {
                    "id": "document1",
                    "document_name": "Document 1",
                    "template": False,
                    "updated": "1640995200",
                    "roles": [],
                },
            ],
        )

    @pytest.fixture
    def sample_folder_content_response(self):
        """Create sample folder content response."""
        return GetFolderByIdResponse(
            id="folder1",
            created="2024-01-01T00:00:00Z",
            name="Folder 1",
            user_id="user123",
            parent_id="root_folder_id",
            system_folder=False,
            shared=False,
            total_documents=2,
            documents=[
                {
                    "id": "template2",
                    "document_name": "Template 2",
                    "template": True,
                    "updated": "1640995200",
                    "roles": [{"name": "Reviewer"}],
                },
                {
                    "id": "document2",
                    "document_name": "Document 2",
                    "template": False,
                    "updated": "1640995200",
                    "roles": [],
                },
            ],
        )

    @pytest.fixture
    def sample_template_groups_response(self):
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
        mock_context,
        mock_client,
        sample_folders_response,
        sample_folder_content_response,
        sample_template_groups_response,
    ):
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

        # Check individual templates from root folder
        root_templates = [t for t in result.templates if t.entity_type == "template" and t.folder_id == "root_folder_id"]
        assert len(root_templates) == 1
        assert root_templates[0].id == "template1"
        assert root_templates[0].name == "Template 1"
        assert root_templates[0].roles == ["Signer", "Approver"]
        assert root_templates[0].is_prepared is True

        # Check individual templates from subfolders
        subfolder_templates = [t for t in result.templates if t.entity_type == "template" and t.folder_id in ["folder1", "folder2"]]
        assert len(subfolder_templates) == 2
        # Check that we have template2 from folder1
        template2 = next((t for t in subfolder_templates if t.id == "template2"), None)
        assert template2 is not None
        assert template2.name == "Template 2"
        assert template2.roles == ["Reviewer"]

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
    async def test_list_all_templates_empty_folders(self, mock_context, mock_client):
        """Test listing templates when there are no folders or templates."""
        # Setup empty response
        empty_folders_response = GetFoldersResponse(
            id="root_folder_id",
            created="2024-01-01T00:00:00Z",
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[],
            total_documents=0,
            documents=[],
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

    @pytest.mark.asyncio
    async def test_list_all_templates_folder_access_error(
        self,
        mock_context,
        mock_client,
        sample_folders_response,
        sample_template_groups_response,
    ):
        """Test handling of folder access errors."""
        # Setup mocks
        mock_client.get_folders.return_value = sample_folders_response
        mock_client.get_folder_by_id.side_effect = Exception("Access denied")
        mock_client.get_document_template_groups.return_value = sample_template_groups_response

        # Call the function
        result = await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify the result still includes templates from root folder and template groups
        assert isinstance(result, TemplateSummaryList)
        assert result.total_count == 3  # 1 from root + 2 template groups (subfolder templates skipped)

        # Verify that non-template documents are filtered out
        templates = [t for t in result.templates if t.entity_type == "template"]
        assert len(templates) == 1  # Only from root folder
        assert templates[0].id == "template1"

    @pytest.mark.asyncio
    async def test_list_all_templates_missing_optional_fields(
        self,
        mock_context,
        mock_client,
    ):
        """Test handling of documents with missing optional fields."""
        # Setup response with minimal data
        folders_response = GetFoldersResponse(
            id="root_folder_id",
            created="2024-01-01T00:00:00Z",
            name="Root Folder",
            user_id="user123",
            parent_id=None,
            system_folder=True,
            shared=False,
            folders=[],
            total_documents=1,
            documents=[
                {
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
        mock_client.get_document_template_groups.return_value = empty_template_groups_response

        # Call the function
        result = await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify the result handles missing fields gracefully
        assert isinstance(result, TemplateSummaryList)
        assert result.total_count == 1

        template = result.templates[0]
        assert template.id == "template_minimal"
        assert template.name == ""  # Default empty string
        assert template.roles == []  # Default empty list
        assert template.last_updated == 0  # Default 0
        assert template.is_prepared is True  # Default True

    @pytest.mark.asyncio
    async def test_list_all_templates_progress_reporting(
        self,
        mock_context,
        mock_client,
        sample_folders_response,
        sample_template_groups_response,
    ):
        """Test that progress is reported correctly."""
        # Setup mocks
        mock_client.get_folders.return_value = sample_folders_response
        mock_client.get_document_template_groups.return_value = sample_template_groups_response

        # Call the function
        await _list_all_templates(mock_context, "test_token", mock_client)

        # Verify progress reporting calls
        expected_calls = [
            ({"progress": 0, "message": "Selecting all folders"},),
            ({"progress": 1, "total": 3, "message": "Processing root folder"},),
            ({"progress": 2, "total": 3, "message": "Processing subfolder {folder.name}"},),
            ({"progress": 3, "total": 3, "message": "Processing template groups"},),
        ]

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
