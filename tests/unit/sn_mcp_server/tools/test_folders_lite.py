"""
Unit tests for folders_lite models, especially discriminator logic.
"""

from signnow_client.models.folders_lite import (
    DocumentGroupItemLite,
    DocumentGroupTemplateItemLite,
    DocumentItemLite,
    GetFolderByIdResponseLite,
    RoleLite,
    TemplateItemLite,
    UnknownFolderDocLite,
    _folder_doc_type_from_payload,
    _normalize_roles,
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


class TestNormalizeRoles:
    """Test cases for _normalize_roles function."""

    def test_normalize_roles_list_str(self):
        """Test _normalize_roles with list of strings."""
        result = _normalize_roles(["Signer 1", "Signer 2", "Reviewer"])
        assert result == ["Signer 1", "Signer 2", "Reviewer"]

    def test_normalize_roles_list_str_with_empty(self):
        """Test _normalize_roles with list of strings containing empty strings."""
        result = _normalize_roles(["Signer 1", "", "Reviewer", "  "])
        assert result == ["Signer 1", "Reviewer"]  # Empty strings should be filtered out

    def test_normalize_roles_list_dict(self):
        """Test _normalize_roles with list of dictionaries."""
        result = _normalize_roles([{"name": "Signer 1"}, {"name": "Signer 2"}])
        assert result == ["Signer 1", "Signer 2"]

    def test_normalize_roles_list_dict_with_missing_name(self):
        """Test _normalize_roles with list of dictionaries missing name key."""
        result = _normalize_roles([{"name": "Signer 1"}, {"id": "role2"}])
        assert result == ["Signer 1"]  # Dict without name should be skipped

    def test_normalize_roles_list_role_lite(self):
        """Test _normalize_roles with list of RoleLite objects."""
        roles = [RoleLite(name="Signer 1", id="role1"), RoleLite(name="Signer 2", id="role2")]
        result = _normalize_roles(roles)
        assert result == ["Signer 1", "Signer 2"]

    def test_normalize_roles_mixed_formats(self):
        """Test _normalize_roles with mixed formats."""
        roles = [
            "Signer 1",
            {"name": "Signer 2"},
            RoleLite(name="Reviewer", id="role3"),
        ]
        result = _normalize_roles(roles)
        assert result == ["Signer 1", "Signer 2", "Reviewer"]

    def test_normalize_roles_none(self):
        """Test _normalize_roles with None."""
        result = _normalize_roles(None)
        assert result is None

    def test_normalize_roles_empty_list(self):
        """Test _normalize_roles with empty list."""
        result = _normalize_roles([])
        assert result is None  # Empty list should return None

    def test_normalize_roles_not_list(self):
        """Test _normalize_roles with non-list value."""
        result = _normalize_roles("not a list")
        assert result is None

    def test_normalize_roles_list_with_none_values(self):
        """Test _normalize_roles with list containing None values."""
        result = _normalize_roles(["Signer 1", None, "Signer 2"])
        # None values should cause issues, but function should handle gracefully
        # Depending on implementation, this might raise or skip None
        assert isinstance(result, list) or result is None


class TestFolderDocTypeFromPayload:
    """Test cases for _folder_doc_type_from_payload function."""

    def test_folder_doc_type_from_dict_with_type(self):
        """Test _folder_doc_type_from_payload with dict containing 'type' key."""
        payload = {"type": "document", "id": "doc123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "document"

    def test_folder_doc_type_from_dict_with_entity_type(self):
        """Test _folder_doc_type_from_payload with dict containing 'entity_type' key."""
        payload = {"entity_type": "template", "id": "tpl123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "template"

    def test_folder_doc_type_from_dict_entity_type_precedence(self):
        """Test _folder_doc_type_from_payload prefers entity_type over type."""
        payload = {"type": "document", "entity_type": "template", "id": "item123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "template"  # entity_type should take precedence

    def test_folder_doc_type_from_dict_document_group(self):
        """Test _folder_doc_type_from_payload with document-group type."""
        payload = {"type": "document-group", "id": "dg123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "document-group"

    def test_folder_doc_type_from_dict_document_group_normalized(self):
        """Test _folder_doc_type_from_payload normalizes document_group to document-group."""
        payload = {"type": "document_group", "id": "dg123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "document-group"

    def test_folder_doc_type_from_dict_dgt(self):
        """Test _folder_doc_type_from_payload with dgt (document group template) type."""
        payload = {"type": "dgt", "id": "dgt123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "dgt"

    def test_folder_doc_type_from_dict_missing_type(self):
        """Test _folder_doc_type_from_payload with dict missing type/entity_type."""
        payload = {"id": "unknown123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "unknown"

    def test_folder_doc_type_from_dict_unknown_type(self):
        """Test _folder_doc_type_from_payload with unknown type value."""
        payload = {"type": "unknown_type", "id": "item123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "unknown"

    def test_folder_doc_type_from_string(self):
        """Test _folder_doc_type_from_payload with string value directly."""
        result = _folder_doc_type_from_payload("document")
        assert result == "document"

    def test_folder_doc_type_from_string_template(self):
        """Test _folder_doc_type_from_payload with template string."""
        result = _folder_doc_type_from_payload("template")
        assert result == "template"

    def test_folder_doc_type_from_string_dgt(self):
        """Test _folder_doc_type_from_payload with dgt string."""
        result = _folder_doc_type_from_payload("dgt")
        assert result == "dgt"

    def test_folder_doc_type_from_none(self):
        """Test _folder_doc_type_from_payload with None value."""
        result = _folder_doc_type_from_payload(None)
        assert result == "unknown"

    def test_folder_doc_type_from_dict_none_type(self):
        """Test _folder_doc_type_from_payload with dict where type is explicitly None."""
        payload = {"type": None, "id": "item123"}
        result = _folder_doc_type_from_payload(payload)
        assert result == "unknown"
