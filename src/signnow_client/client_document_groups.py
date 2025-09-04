"""
SignNow API Client - Document Groups and Template Groups Methods

Methods for working with document groups and document group templates.
"""

import httpx

from .exceptions import (
    SignNowAPIError,
    SignNowAPITimeoutError,
)
from .models import (
    AddTemplateToDocumentGroupTemplateRequest,
    AddTemplateToDocumentGroupTemplateResponse,
    CancelFreeformInviteRequest,
    CreateDocumentGroupEmbeddedEditorRequest,
    CreateDocumentGroupEmbeddedSendingRequest,
    CreateDocumentGroupFromTemplateRequest,
    CreateDocumentGroupFromTemplateResponse,
    CreateDocumentGroupRequest,
    CreateDocumentGroupResponse,
    CreateDocumentGroupTemplateFromGroupRequest,
    CreateDocumentGroupTemplateRequest,
    CreateDocumentGroupTemplateResponse,
    CreateEmbeddedEditorResponse,
    CreateEmbeddedInviteRequest,
    CreateEmbeddedSendingResponse,
    CreateFieldInviteRequest,
    CreateFieldInviteResponse,
    CreateFreeformInviteRequest,
    CreateFreeformInviteResponse,
    DocumentGroupsResponse,
    DocumentGroupTemplatesResponse,
    EditDocumentGroupTemplateRecipientsRequest,
    EmbeddedInviteLinkResponse,
    EmbeddedInviteResponse,
    GenerateEmbeddedInviteLinkRequest,
    GetDocumentGroupResponse,
    GetDocumentGroupTemplateRecipientsResponse,
    GetDocumentGroupV2Response,
    GetFieldInviteResponse,
    GetRecipientsResponse,
    SendEmailRequest,
)


class DocumentGroupClientMixin:
    """Mixin class for document group and template group related methods"""

    def get_document_template_groups(self, token: str, limit: int = 50, offset: int = 0) -> DocumentGroupTemplatesResponse:
        """
        Get document template groups list from SignNow API.

        Args:
            token: Access token for authentication
            limit: Maximum number of template groups to return
            offset: Number of template groups to skip for pagination

        Returns:
            Validated DocumentGroupTemplatesResponse model
        """

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        params = {"limit": limit, "offset": offset}

        return self._get("/user/documentgroup/templates", headers=headers, params=params, validate_model=DocumentGroupTemplatesResponse)

    def get_document_groups(self, token: str, limit: int = 50, offset: int = 0) -> DocumentGroupsResponse:
        """
        Get document groups list from SignNow API.

        Args:
            token: Access token for authentication
            limit: Maximum number of document groups to return
            offset: Number of document groups to skip for pagination

        Returns:
            Validated DocumentGroupsResponse model
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        params = {"limit": limit, "offset": offset}

        return self._get("/user/documentgroups", headers=headers, params=params, validate_model=DocumentGroupsResponse)

    def get_document_group(self, token: str, document_group_id: str) -> GetDocumentGroupResponse:
        """
        Get a specific document group by ID from SignNow API.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group to retrieve

        Returns:
            Validated GetDocumentGroupResponse model
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/documentgroup/{document_group_id}", headers=headers, validate_model=GetDocumentGroupResponse)

    def get_document_group_v2(self, token: str, document_group_id: str) -> GetDocumentGroupV2Response:
        """
        Get document group info (v.2).

        This endpoint is used for getting basic information about document groups. Owner of a group,
        as well as invited users (in any invite on any step), can access basic information.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group to retrieve

        Returns:
            Validated GetDocumentGroupV2Response model
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/v2/document-groups/{document_group_id}", headers=headers, validate_model=GetDocumentGroupV2Response)

    def create_document_group(self, token: str, request_data: CreateDocumentGroupRequest) -> CreateDocumentGroupResponse:
        """
        Create a document group from multiple documents.

        This endpoint creates a new document group by combining multiple documents.

        Args:
            token: Access token for authentication
            request_data: Request data with document IDs and group name

        Returns:
            Validated CreateDocumentGroupResponse model with the created group ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post("/documentgroup", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateDocumentGroupResponse)

    def create_embedded_invite(self, token: str, document_group_id: str, request_data: CreateEmbeddedInviteRequest) -> EmbeddedInviteResponse:
        """
        Create embedded signing invite for a document group.

        This endpoint allows users to create an embedded signing invite for a document group.
        Once the invite is created, generate an embedded signing link using the invite ID.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            request_data: Embedded invite request data with signers and documents

        Returns:
            Validated EmbeddedInviteResponse model with the created invite ID

        Raises:
            SignNowAPIError: When current user is not the document group owner
            SignNowAPIError: When document group has no document with fields
            SignNowAPIError: When document group has active invites
            SignNowAPIError: When role doesn't exist in the document
            SignNowAPIError: When not all document roles were used
            SignNowAPIError: When document owner's email was used as signer's email
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-groups/{document_group_id}/embedded-invites",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=EmbeddedInviteResponse,
        )

    def generate_embedded_invite_link(self, token: str, document_group_id: str, embedded_invite_id: str, request_data: GenerateEmbeddedInviteLinkRequest) -> EmbeddedInviteLinkResponse:
        """
        Generate embedded invite link for document group signing.

        This endpoint allows users to generate a link for the document group embedded invite.
        Use the embedded invite ID from the create_embedded_invite response.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            embedded_invite_id: ID of the embedded invite
            request_data: Link generation request data with email and auth method

        Returns:
            Validated EmbeddedInviteLinkResponse model with the generated signing link
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-groups/{document_group_id}/embedded-invites/{embedded_invite_id}/link",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=EmbeddedInviteLinkResponse,
        )

    def create_freeform_invite(self, token: str, document_group_id: str, request_data: CreateFreeformInviteRequest) -> CreateFreeformInviteResponse:
        """
        Create a FreeForm invite for a document group.

        This endpoint allows users to create a freeform invite for a document group.
        Freeform invites are simpler than embedded invites and don't require role mapping.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            request_data: Freeform invite request data with recipients and settings

        Returns:
            Validated CreateFreeformInviteResponse model with the created invite ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-groups/{document_group_id}/free-form-invites",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=CreateFreeformInviteResponse,
        )

    def cancel_freeform_invite(self, token: str, document_group_id: str, freeform_invite_id: str, request_data: CancelFreeformInviteRequest) -> bool:
        """
        Cancel the document group FreeForm invite for all signers.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            freeform_invite_id: ID of the document group FreeForm invite
            request_data: Cancellation request data with reason and timestamp

        Returns:
            True if successful (204 response)
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        self._post(f"/v2/document-groups/{document_group_id}/free-form-invites/{freeform_invite_id}/cancel", headers=headers, json_data=request_data.model_dump(exclude_none=True))
        return True

    def create_field_invite(self, token: str, document_group_id: str, request_data: CreateFieldInviteRequest) -> CreateFieldInviteResponse:
        """
        Create a field invite for signing a document group.

        This endpoint allows users to create an invite for signing a document group with a multistep workflow.
        Each invite step includes order, invite_emails, and invite_actions.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            request_data: Field invite request data with steps and settings

        Returns:
            Validated CreateFieldInviteResponse model with the created invite ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(f"/documentgroup/{document_group_id}/groupinvite", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateFieldInviteResponse)

    def get_field_invite(self, token: str, document_group_id: str, invite_id: str) -> GetFieldInviteResponse:
        """
        Get document group invite information.

        This endpoint returns document group invite information, including the status of each step and action.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            invite_id: ID of the document group invite

        Returns:
            Validated GetFieldInviteResponse model with invite status and steps
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/documentgroup/{document_group_id}/groupinvite/{invite_id}", headers=headers, validate_model=GetFieldInviteResponse)

    def send_document_group_email(self, token: str, document_group_id: str, request_data: SendEmailRequest) -> bool:
        """
        Send an email with a document group.

        A receiver can view or download the documents. A document group can be sent by either
        an owner, signer, or viewer of the document group.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group
            request_data: Email request data with recipients and settings

        Returns:
            True if successful (204 response)
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        self._post(f"/v2/document-groups/{document_group_id}/send-email", headers=headers, json_data=request_data.model_dump(exclude_none=True))
        return True

    def get_document_group_recipients(self, token: str, document_group_id: str) -> GetRecipientsResponse:
        """
        Get the list of recipients for a document group invite.

        This endpoint retrieves the list of recipients for a document group invite.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group

        Returns:
            Validated GetRecipientsResponse model with recipients and document mappings
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/v2/document-groups/{document_group_id}/recipients", headers=headers, validate_model=GetRecipientsResponse)

    def create_document_group_embedded_editor(self, token: str, document_group_id: str, request_data: CreateDocumentGroupEmbeddedEditorRequest) -> CreateEmbeddedEditorResponse:
        """
        Create link for document group embedded editor.

        This endpoint creates a link that allows users of the app to edit a document
        group without sending it for signature.

        Args:
            token: Access token for authentication
            document_group_id: ID of the document group to open in the embedded editor
            request_data: Request data with redirect settings and expiration

        Returns:
            Validated CreateEmbeddedEditorResponse model with embedded editor URL
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-groups/{document_group_id}/embedded-editor",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=CreateEmbeddedEditorResponse,
        )

    def create_document_group_embedded_sending(self, token: str, document_group_id: str, request_data: CreateDocumentGroupEmbeddedSendingRequest) -> CreateEmbeddedSendingResponse:
        """
        Create link for document group embedded sending.

        This endpoint allows users to create a link for embedded document group sending.
        Add the `type` attribute to specify the sending step at which the embedded link
        should open and to control what actions the sender can perform.

        Args:
            token: Access token for authentication
            document_group_id: ID of the requested document group
            request_data: Request data with type, redirect settings and expiration

        Returns:
            Validated CreateEmbeddedSendingResponse model with embedded sending URL(s)

        Raises:
            SignNowAPIError: If user is not document group owner or group not found
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-groups/{document_group_id}/embedded-sending",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=CreateEmbeddedSendingResponse,
        )

    def create_document_group_template(self, token: str, request_data: CreateDocumentGroupTemplateRequest) -> CreateDocumentGroupTemplateResponse:
        """
        Create an empty document group template.

        This endpoint allows users to create an empty document group template.
        Once the document group template is created, users can add one or more
        templates or documents to this document group template.

        Args:
            token: Access token for authentication
            request_data: Request data with template name and optional folder ID

        Returns:
            Validated CreateDocumentGroupTemplateResponse model with template ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post("/v2/document-group-templates", headers=headers, json_data=request_data.model_dump(exclude_none=True), validate_model=CreateDocumentGroupTemplateResponse)

    def create_document_group_template_from_group(self, token: str, doc_group_id: str, request_data: CreateDocumentGroupTemplateFromGroupRequest) -> bool:
        """
        Create document group template from document group.

        This endpoint allows users to create a new Document Group Template from
        a Document Group in any status. As a result, user gets one Document Group
        Template and separate Templates from each document in the Document Group.

        Args:
            token: Access token for authentication
            doc_group_id: ID of the document group
            request_data: Request data with template name and optional folder ID

        Returns:
            True if template creation was scheduled successfully
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        response = self._post(f"/v2/document-groups/{doc_group_id}/document-group-template", headers=headers, json_data=request_data.model_dump(exclude_none=True))

        # This endpoint returns 202 (Accepted) status
        return True

    def add_template_to_document_group_template(self, token: str, doc_group_template_id: str, request_data: AddTemplateToDocumentGroupTemplateRequest) -> AddTemplateToDocumentGroupTemplateResponse:
        """
        Add template to document group template.

        This endpoint allows users to add a document or template to the specific
        document group template. Uploaded documents are automatically converted to templates.

        Note: Only one parameter (document_id or template_id) should be provided per request.

        Args:
            token: Access token for authentication
            doc_group_template_id: ID of the document group template
            request_data: Request data with document_id or template_id

        Returns:
            Validated AddTemplateToDocumentGroupTemplateResponse model with added template ID
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-group-templates/{doc_group_template_id}/templates",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=AddTemplateToDocumentGroupTemplateResponse,
        )

    def get_document_group_template_recipients(self, token: str, doc_group_template_id: str) -> GetDocumentGroupTemplateRecipientsResponse:
        """
        Get document group template recipients.

        This endpoint allows users to get a list of the document group template recipients.

        Args:
            token: Access token for authentication
            doc_group_template_id: ID of the document group template

        Returns:
            Validated GetDocumentGroupTemplateRecipientsResponse model with recipients data
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        return self._get(f"/v2/document-group-templates/{doc_group_template_id}/recipients", headers=headers, validate_model=GetDocumentGroupTemplateRecipientsResponse)

    def edit_document_group_template_recipients(self, token: str, doc_group_template_id: str, request_data: EditDocumentGroupTemplateRecipientsRequest) -> bool:
        """
        Edit document group template recipients.

        This endpoint allows users to edit the recipients of the document group template.
        Users can edit recipients' emails, roles, signing order, document attributes,
        signature invite email attributes, and authentication settings.

        Args:
            token: Access token for authentication
            doc_group_template_id: ID of the document group template
            request_data: Request data with recipients, unmapped documents, and cc

        Returns:
            True if recipients were updated successfully
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        try:
            response = self.http.put(f"/v2/document-group-templates/{doc_group_template_id}/recipients", headers=headers, json=request_data.model_dump(exclude_none=True))
            response.raise_for_status()
            # For 204 No Content, we don't need to parse JSON
            return True
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e)
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in edit_document_group_template_recipients request: {e}") from e

    def create_document_group_from_template(self, token: str, unique_id: str, request_data: CreateDocumentGroupFromTemplateRequest) -> CreateDocumentGroupFromTemplateResponse:
        """
        Create document group from template.

        This endpoint allows the creation of a document group from the document group template.

        Args:
            token: Access token for authentication
            unique_id: Document group template unique ID
            request_data: Request data with group name and optional settings

        Returns:
            Validated CreateDocumentGroupFromTemplateResponse model with created group data
        """

        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        return self._post(
            f"/v2/document-group-templates/{unique_id}/document-group",
            headers=headers,
            json_data=request_data.model_dump(exclude_none=True),
            validate_model=CreateDocumentGroupFromTemplateResponse,
        )
