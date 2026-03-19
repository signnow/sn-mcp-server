"""Unit tests for DocumentFieldJsonAttributes model in templates_and_documents module."""

from signnow_client.models.templates_and_documents import DocumentFieldJsonAttributes


class TestDocumentFieldJsonAttributes:
    """Test cases for DocumentFieldJsonAttributes model."""

    def test_document_field_json_attributes_name_optional_when_missing(self) -> None:
        """Validate from dict with no name key results in name being None."""
        model = DocumentFieldJsonAttributes.model_validate({"prefilled_text": "hello"})
        assert model.name is None

    def test_document_field_json_attributes_name_present(self) -> None:
        """Validate from dict with name key results in name equaling the value."""
        model = DocumentFieldJsonAttributes.model_validate({"name": "signature_field"})
        assert model.name == "signature_field"

    def test_document_field_json_attributes_empty_dict_no_validation_error(self) -> None:
        """Validate from empty dict does not raise ValidationError."""
        model = DocumentFieldJsonAttributes.model_validate({})
        assert model.name is None
        assert model.prefilled_text is None
