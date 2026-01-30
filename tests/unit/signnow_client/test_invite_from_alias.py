"""
Unit tests for invite request models and serialization.
"""

from unittest.mock import Mock

from signnow_client.client_documents import DocumentClientMixin
from signnow_client.models.templates_and_documents import (
    CreateDocumentFieldInviteRequest,
    CreateDocumentFreeformInviteRequest,
)


class _DummyDocumentClient(DocumentClientMixin):
    def __init__(self):
        self.last_post = None

    def _post(self, url: str, headers=None, data=None, json_data=None, validate_model=None):
        self.last_post = {"url": url, "headers": headers, "data": data, "json_data": json_data, "validate_model": validate_model}
        if validate_model is None:
            return None
        if validate_model.__name__ == "CreateDocumentFieldInviteResponse":
            return validate_model.model_validate({"status": "ok"})
        if validate_model.__name__ == "CreateDocumentFreeformInviteResponse":
            return validate_model.model_validate({"result": "ok", "id": "invite123", "callback_url": "https://example.com/callback"})
        # Fallback for any other response models used in this test module
        return validate_model.model_validate({})


def test_create_document_field_invite_request_accepts_from_field_name_and_serializes_alias():
    req = CreateDocumentFieldInviteRequest(document_id="doc123", to=[], from_="sample-apps@signnow.com")
    assert req.from_ == "sample-apps@signnow.com"

    dumped = req.model_dump(exclude_none=True, by_alias=True)
    assert dumped["from"] == "sample-apps@signnow.com"
    assert "from_" not in dumped


def test_create_document_freeform_invite_request_accepts_from_field_name_and_serializes_alias():
    req = CreateDocumentFreeformInviteRequest(to="signer@example.com", from_="sample-apps@signnow.com")
    assert req.from_ == "sample-apps@signnow.com"

    dumped = req.model_dump(exclude_none=True, by_alias=True)
    assert dumped["from"] == "sample-apps@signnow.com"
    assert "from_" not in dumped


def test_client_document_field_invite_uses_by_alias_true_when_dumping():
    client = _DummyDocumentClient()
    request_data = Mock()
    request_data.model_dump.return_value = {"from": "sample-apps@signnow.com"}

    client.create_document_field_invite(token="t", document_id="doc123", request_data=request_data)
    request_data.model_dump.assert_called_once_with(exclude_none=True, by_alias=True)


def test_client_document_freeform_invite_uses_by_alias_true_when_dumping():
    client = _DummyDocumentClient()
    request_data = Mock()
    request_data.model_dump.return_value = {"from": "sample-apps@signnow.com"}

    client.create_document_freeform_invite(token="t", document_id="doc123", request_data=request_data)
    request_data.model_dump.assert_called_once_with(exclude_none=True, by_alias=True)
