"""
Unit tests for folders_lite models, especially discriminator logic.
"""

from signnow_client.models.folders_lite import (
    DocumentGroupItemLite,
    DocumentGroupTemplateItemLite,
    DocumentItemLite,
    GetFolderByIdResponseLite,
    TemplateItemLite,
    UnknownFolderDocLite,
)


class TestFoldersLiteDiscriminator:
    """Test cases for folder document discriminator logic."""

    def test_discriminator_document_type(self):
        """Test discriminator correctly identifies document type."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
        }
        doc = DocumentItemLite(**payload)
        assert doc.type == "document"
        assert doc.id == "doc123"

    def test_discriminator_template_type(self):
        """Test discriminator correctly identifies template type."""
        payload = {
            "type": "template",
            "id": "tpl123",
            "document_name": "Test Template",
            "user_id": "user123",
        }
        doc = TemplateItemLite(**payload)
        assert doc.type == "template"
        assert doc.id == "tpl123"

    def test_discriminator_document_group_type(self):
        """Test discriminator correctly identifies document-group type."""
        payload = {
            "type": "document-group",
            "id": "dg123",
            "document_group_name": "Test Group",
            "user_id": "user123",
        }
        doc = DocumentGroupItemLite(**payload)
        assert doc.type == "document-group"
        assert doc.id == "dg123"

    def test_discriminator_document_group_normalized(self):
        """Test discriminator normalizes document_group to document-group."""
        payload = {
            "type": "document_group",
            "id": "dg123",
            "document_group_name": "Test Group",
            "user_id": "user123",
        }
        doc = DocumentGroupItemLite(**payload)
        assert doc.type == "document-group"

    def test_discriminator_dgt_type(self):
        """Test discriminator correctly identifies dgt type."""
        payload = {
            "type": "dgt",
            "id": "dgt123",
            "document_group_name": "Test DGT",
            "user_id": "user123",
        }
        doc = DocumentGroupTemplateItemLite(**payload)
        assert doc.type == "dgt"
        assert doc.id == "dgt123"

    def test_discriminator_entity_type_alias(self):
        """Test discriminator uses entity_type as alias for type."""
        payload = {
            "entity_type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
        }
        doc = DocumentItemLite(**payload)
        assert doc.type == "document"

    def test_discriminator_missing_type_unknown(self):
        """Test discriminator handles missing type/entity_type as unknown."""
        payload = {
            "id": "unknown123",
            "document_name": "Unknown Item",
            "user_id": "user123",
        }
        # Should create UnknownFolderDocLite when type is missing
        doc = UnknownFolderDocLite(**payload)
        assert doc.type == "unknown"
        assert doc.id == "unknown123"

    def test_discriminator_unknown_type_value(self):
        """Test discriminator handles unknown type values."""
        payload = {
            "type": "unknown_type",
            "id": "unknown123",
            "document_name": "Unknown Item",
            "user_id": "user123",
        }
        # Should create UnknownFolderDocLite for unknown types
        doc = UnknownFolderDocLite(**payload)
        assert doc.type == "unknown"

    def test_int_from_any_string_value(self):
        """Test IntFromAny handles string values."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "page_count": "10",
            "created": "1234567890",
            "updated": "1234567890",
        }
        doc = DocumentItemLite(**payload)
        assert doc.page_count == 10
        assert doc.created == 1234567890
        assert doc.updated == 1234567890

    def test_int_from_any_int_value(self):
        """Test IntFromAny handles int values."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "page_count": 10,
            "created": 1234567890,
            "updated": 1234567890,
        }
        doc = DocumentItemLite(**payload)
        assert doc.page_count == 10
        assert doc.created == 1234567890
        assert doc.updated == 1234567890

    def test_int_from_any_none_value(self):
        """Test IntFromAny handles None values."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "page_count": None,
            "created": None,
            "updated": None,
        }
        doc = DocumentItemLite(**payload)
        assert doc.page_count is None
        assert doc.created is None
        assert doc.updated is None

    def test_int_from_any_invalid_value(self):
        """Test IntFromAny handles invalid values gracefully."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "page_count": "invalid",
            "created": "not_a_number",
            "updated": {},
        }
        doc = DocumentItemLite(**payload)
        # Invalid values should be converted to None
        assert doc.page_count is None
        assert doc.created is None
        assert doc.updated is None

    def test_get_folder_by_id_response_lite_documents(self):
        """Test GetFolderByIdResponseLite with mixed document types."""
        payload = {
            "id": "folder123",
            "name": "Test Folder",
            "user_id": "user123",
            "created": 1234567890,
            "documents": [
                {
                    "type": "document",
                    "id": "doc1",
                    "document_name": "Document 1",
                    "user_id": "user123",
                },
                {
                    "type": "template",
                    "id": "tpl1",
                    "document_name": "Template 1",
                    "user_id": "user123",
                },
                {
                    "type": "document-group",
                    "id": "dg1",
                    "document_group_name": "Group 1",
                    "user_id": "user123",
                },
                {
                    "type": "dgt",
                    "id": "dgt1",
                    "document_group_name": "DGT 1",
                    "user_id": "user123",
                },
                {
                    "id": "unknown1",
                    "document_name": "Unknown Item",
                    "user_id": "user123",
                },
            ],
        }
        response = GetFolderByIdResponseLite(**payload)
        assert len(response.documents) == 5
        # Check that discriminator correctly identified each type
        assert isinstance(response.documents[0], DocumentItemLite)
        assert isinstance(response.documents[1], TemplateItemLite)
        assert isinstance(response.documents[2], DocumentGroupItemLite)
        assert isinstance(response.documents[3], DocumentGroupTemplateItemLite)
        assert isinstance(response.documents[4], UnknownFolderDocLite)

    def test_roles_normalization_string_list(self):
        """Test roles normalization with list of strings."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "roles": ["Signer 1", "Signer 2"],
        }
        doc = DocumentItemLite(**payload)
        assert doc.roles == ["Signer 1", "Signer 2"]

    def test_roles_normalization_role_lite_list(self):
        """Test roles normalization with list of RoleLite objects."""
        from signnow_client.models.folders_lite import RoleLite

        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "roles": [
                {"name": "Signer 1", "id": "role1"},
                {"name": "Signer 2", "id": "role2"},
            ],
        }
        doc = DocumentItemLite(**payload)
        # Roles should be normalized to list[str]
        assert doc.roles == ["Signer 1", "Signer 2"]

    def test_roles_normalization_mixed(self):
        """Test roles normalization with mixed formats."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "roles": [
                "Signer 1",
                {"name": "Signer 2"},
            ],
        }
        doc = DocumentItemLite(**payload)
        # Roles should be normalized to list[str]
        assert doc.roles == ["Signer 1", "Signer 2"]

    def test_roles_normalization_none(self):
        """Test roles normalization with None."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "roles": None,
        }
        doc = DocumentItemLite(**payload)
        assert doc.roles is None

    def test_roles_normalization_empty_list(self):
        """Test roles normalization with empty list."""
        payload = {
            "type": "document",
            "id": "doc123",
            "document_name": "Test Document",
            "user_id": "user123",
            "roles": [],
        }
        doc = DocumentItemLite(**payload)
        assert doc.roles is None  # Empty list should be normalized to None
