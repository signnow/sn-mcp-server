"""
SignNow API Client - Document and Template Methods

Methods for working with individual documents and templates.
"""

import httpx

from .exceptions import SignNowAPIError, SignNowAPITimeoutError
from .models import (
    CancelDocumentFieldInviteRequest,
    CancelDocumentFieldInviteResponse,
    CreateDocumentEmbeddedEditorRequest,
    CreateDocumentEmbeddedInviteRequest,
    CreateDocumentEmbeddedInviteResponse,
    CreateDocumentEmbeddedSendingRequest,
    CreateDocumentFieldInviteRequest,
    CreateDocumentFieldInviteResponse,
    CreateDocumentFreeformInviteRequest,
    CreateDocumentFreeformInviteResponse,
    CreateDocumentFromTemplateRequest,
    CreateDocumentFromTemplateResponse,
    CreateDocumentFromUrlRequest,
    CreateDocumentFromUrlResponse,
    CreateEmbeddedEditorResponse,
    CreateEmbeddedSendingResponse,
    CreateTemplateRequest,
    CreateTemplateResponse,
    DocumentDownloadLinkResponse,
    DocumentResponse,
    GenerateDocumentEmbeddedInviteLinkRequest,
    GenerateDocumentEmbeddedInviteLinkResponse,
    GetDocumentFieldsResponse,
    GetDocumentHistoryResponse,
    MergeDocumentsRequest,
    MergeDocumentsResponse,
    PrefillTextFieldsRequest,
    UploadDocumentResponse,
)


class DocumentClientMixin:
    """Mixin class for document and template related methods"""

    def upload_document(self, token: str, file_content: bytes, filename: str, check_fields: bool = True) -> UploadDocumentResponse:
        """
        Upload a document to SignNow.

        This endpoint uploads a document file to SignNow and returns the document ID.

        Args:
            token: Access token for authentication
            file_content: Document file content as bytes
            filename: Name of the file to upload
            check_fields: Whether to check for fields in the document (default: True)

        Returns:
            Validated UploadDocumentResponse model with the uploaded document ID
        """

        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": (filename, file_content, "application/octet-stream")}

        data = {"check_fields": "true" if check_fields else "false"}

        return self._post_multipart("/document", headers=headers, files=files, data=data, validate_model=UploadDocumentResponse)

    def get_document_download_link(self, token: str, document_id: str) -> DocumentDownloadLinkResponse:
        """
        Get download link for a document.

        This endpoint generates a download link for a specific document.

        Args:
            token: Access token for authentication
            document_id: ID of the document to download

        Returns:
            Validated DocumentDownloadLinkResponse model with the download link
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(f"/document/{document_id}/download/link", headers=headers, validate_model=DocumentDownloadLinkResponse)

    def create_document_from_url(self, token: str, request_data: CreateDocumentFromUrlRequest) -> CreateDocumentFromUrlResponse:
        """
        Create a document from a URL.

        This endpoint creates a new document from a file URL.

        Args:
            token: Access token for authentication
            request_data: Request data with URL and field checking option

        Returns:
            Validated CreateDocumentFromUrlResponse model with the created document ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post("/v2/documents/url", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateDocumentFromUrlResponse)

    def prefill_text_fields(self, token: str, document_id: str, request_data: PrefillTextFieldsRequest) -> bool:
        """
        Prefill text fields in a document.

        This endpoint allows users to prefill text fields in a document before sending for signature.
        Only fields of type text can be prefilled.

        Args:
            token: Access token for authentication
            document_id: ID of the document to prefill fields in
            request_data: Request data with fields to prefill

        Returns:
            True if successful (204 response)
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        try:
            response = self.http.put(f"/v2/documents/{document_id}/prefill-texts", headers=headers, json=request_data.model_dump(exclude_none=True))
            response.raise_for_status()
            # For 204 No Content, we don't need to parse JSON
            return True
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e)
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in prefill_text_fields request: {e}") from e

    def get_document(self, token: str, document_id: str, include_integration_objects: bool = False) -> DocumentResponse:
        """
        Get document details.

        This endpoint returns details of a specific document including metadata, fields,
        signatures, invites, roles, and settings.

        Args:
            token: Access token for authentication
            document_id: ID of the document to retrieve
            include_integration_objects: Include smart fields in response

        Returns:
            Validated DocumentResponse model with complete document information
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        params = {}
        if include_integration_objects:
            params["include"] = "integration_objects"

        return self._get(f"/document/{document_id}", headers=headers, params=params, validate_model=DocumentResponse)

    def merge_documents(self, token: str, request_data: MergeDocumentsRequest) -> MergeDocumentsResponse:
        """
        Merge multiple documents into one.

        This endpoint merges existing documents into a single document.

        Args:
            token: Access token for authentication
            request_data: Request data with document IDs and merge settings

        Returns:
            Validated MergeDocumentsResponse model with the merged document ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post("/document/merge", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=MergeDocumentsResponse)

    def get_document_fields(self, token: str, document_id: str) -> GetDocumentFieldsResponse:
        """
        Get fields data from completed document.

        This endpoint retrieves contents from the fields completed by the signer.

        Args:
            token: Access token for authentication
            document_id: ID of the document to get fields from

        Returns:
            Validated GetDocumentFieldsResponse model with field data and pagination
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/v2/documents/{document_id}/fields", headers=headers, validate_model=GetDocumentFieldsResponse)

    def get_document_history(self, token: str, document_id: str) -> GetDocumentHistoryResponse:
        """
        Get document history.

        This endpoint returns the complete history of a document including all events
        and optionally email history events.

        Args:
            token: Access token for authentication
            document_id: ID of the document to get history for

        Returns:
            Validated GetDocumentHistoryResponse model with document and email history
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/document/{document_id}/historyfull", headers=headers, validate_model=GetDocumentHistoryResponse)

    def create_document_embedded_invite(self, token: str, document_id: str, request_data: CreateDocumentEmbeddedInviteRequest) -> CreateDocumentEmbeddedInviteResponse:
        """
        Create embedded signing invite for a document.

        This endpoint allows users to create an embedded signing invite for a document.
        Once the invite is created, generate an embedded signing link using
        generate_document_embedded_invite_link() with the ID you got in the response.

        Before sending your request, ensure the following:
        - You are the owner of the document to be signed
        - The invite is being created for a document (not a template)
        - Your document contains fields
        - The document is not part of any other invite (pending or signed)
        - Signers' email addresses are unique and do not exceed 150 characters
        - All roles or role IDs in the document are included in the invite
        - The document owner cannot be assigned as a signer

        Args:
            token: Access token for authentication
            document_id: ID of the document to create invite for
            request_data: Request data with invites and optional name formula

        Returns:
            Validated CreateDocumentEmbeddedInviteResponse model with created invite IDs
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/documents/{document_id}/embedded-invites",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=CreateDocumentEmbeddedInviteResponse,
        )

    def generate_document_embedded_invite_link(
        self, token: str, document_id: str, field_invite_id: str, request_data: GenerateDocumentEmbeddedInviteLinkRequest
    ) -> GenerateDocumentEmbeddedInviteLinkResponse:
        """
        Generate embedded invite link for a document.

        This endpoint allows users to generate a link for the document embedded invite.
        Retrieve the field invite ID from the response of create_document_embedded_invite().

        Args:
            token: Access token for authentication
            document_id: ID of the document
            field_invite_id: ID of the embedded invite from create_document_embedded_invite()
            request_data: Request data with auth_method and optional expiration settings

        Returns:
            Validated GenerateDocumentEmbeddedInviteLinkResponse model with generated link
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/documents/{document_id}/embedded-invites/{field_invite_id}/link",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=GenerateDocumentEmbeddedInviteLinkResponse,
        )

    def create_document_embedded_editor(self, token: str, document_id: str, request_data: CreateDocumentEmbeddedEditorRequest) -> CreateEmbeddedEditorResponse:
        """
        Create link for document embedded editor.

        This endpoint creates a link that can be used to embed SignNow document editor
        into an app. This link allows users of the app to edit a document without
        sending it for signature.

        Note! To open a document in SignNow editor, please make sure that:
        - This document has not been sent for signature or signed
        - This document is not deleted or archived

        Args:
            token: Access token for authentication
            document_id: ID of the document to open in the embedded editor
            request_data: Request data with redirect settings and expiration

        Returns:
            Validated CreateEmbeddedEditorResponse model with embedded editor URL
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(f"/v2/documents/{document_id}/embedded-editor", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateEmbeddedEditorResponse)

    def create_document_embedded_sending(self, token: str, document_id: str, request_data: CreateDocumentEmbeddedSendingRequest) -> CreateEmbeddedSendingResponse:
        """
        Create link for document embedded sending.

        This endpoint creates a link to the Invite settings page for a specific document
        (for third party users to prepare and send the invite to sign).

        Args:
            token: Access token for authentication
            document_id: ID of the requested document
            request_data: Request data with type, redirect settings and expiration

        Returns:
            Validated CreateEmbeddedSendingResponse model with embedded sending URL

        Raises:
            SignNowAPIError: If document requirements are not met
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(f"/v2/documents/{document_id}/embedded-sending", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateEmbeddedSendingResponse)

    def create_template(self, token: str, request_data: CreateTemplateRequest) -> CreateTemplateResponse:
        """
        Create template from document.

        Creates a template by flattening an existing document.

        Template - an entity that holds the structure of a document and serves
        for generating its copies. SignNow users cannot make a template without
        uploading a document first. They can generate (clone) a new instance
        of a document from it.

        When you create an invite using a template, recipients sign the instance
        of this template - a document. The instance can be customized specifically
        for the recipient, for example, prefilled with the account info. Templates
        can be shared within a team and edited only by the owner.

        Args:
            token: Access token for authentication
            request_data: Request data with document ID and template name

        Returns:
            Validated CreateTemplateResponse model with template ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post("/template", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateTemplateResponse)

    def create_document_from_template(self, token: str, template_id: str, request_data: CreateDocumentFromTemplateRequest | None = None) -> CreateDocumentFromTemplateResponse:
        """
        Create document from template.

        Creates a new document copy out of template. If a name is not supplied
        than it will default to the original template name.

        Args:
            token: Access token for authentication
            template_id: ID of the template to copy from
            request_data: Optional request data with custom document name

        Returns:
            Validated CreateDocumentFromTemplateResponse model with document ID and name
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        json_data = None
        if request_data:
            json_data = request_data.model_dump(exclude_none=True)

        return self._post(f"/template/{template_id}/copy", headers=headers, json_data=json_data, validate_model=CreateDocumentFromTemplateResponse)

    def create_document_field_invite(self, token: str, document_id: str, request_data: CreateDocumentFieldInviteRequest) -> CreateDocumentFieldInviteResponse:
        """
        Create document field invite.

        This endpoint allows users to create and send a field invite to sign a document.
        Invite payload varies for a document that contains or doesn't contain fields.

        For an invite with fields sent by email, see this page.
        For an invite without fields, see Freeform invite.
        For an invite with fields sent by SMS, see SMS invite.

        Learn more about an Invite to sign a document.

        Args:
            token: Access token for authentication
            document_id: ID of the document
            request_data: Request data with recipients, settings, and customization options

        Returns:
            Validated CreateDocumentFieldInviteResponse model with invite status
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(f"/document/{document_id}/invite", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateDocumentFieldInviteResponse)

    def cancel_document_field_invite(self, token: str, document_id: str, request_data: CancelDocumentFieldInviteRequest) -> CancelDocumentFieldInviteResponse:
        """
        Cancel document field invite.

        Cancels an invite to a document.

        Args:
            token: Access token for authentication
            document_id: ID of the document
            request_data: Request data with cancellation reason

        Returns:
            Validated CancelDocumentFieldInviteResponse model with cancellation status
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._put(f"/document/{document_id}/fieldinvitecancel", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CancelDocumentFieldInviteResponse)

    def create_document_freeform_invite(self, token: str, document_id: str, request_data: CreateDocumentFreeformInviteRequest) -> CreateDocumentFreeformInviteResponse:
        """
        Create document freeform invite.

        This endpoint allows users to create and send a freeform invite to sign a document.
        Freeform invites are for documents that don't contain fields; recipients add their
        signature anywhere on the document.

        Args:
            token: Access token for authentication
            document_id: ID of the document
            request_data: Request data with recipients, settings, and customization options

        Returns:
            Validated CreateDocumentFreeformInviteResponse model with invite status
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(f"/document/{document_id}/invite", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateDocumentFreeformInviteResponse)
