"""
Document Tools

Tools for working with documents in SignNow.
"""

from typing import Literal

from signnow_client import SignNowAPIClient
from signnow_client.models.document_groups import GetDocumentGroupV2Response
from signnow_client.models.templates_and_documents import (
    DocumentResponse,
)

from .models import (
    DocumentField,
    DocumentGroup,
    DocumentGroupDocument,
    UpdateDocumentFields,
    UpdateDocumentFieldsResponse,
    UpdateDocumentFieldsResult,
    UploadDocumentResponse,
)


def _upload_document(file_content: bytes, filename: str, check_fields: bool, token: str, client: SignNowAPIClient) -> UploadDocumentResponse:
    """
    Upload a document to SignNow.

    Args:
        file_content: Document file content as bytes
        filename: Name of the file to upload
        check_fields: Whether to check for fields in the document
        token: Access token for authentication
        client: SignNow API client instance

    Returns:
        UploadDocumentResponse with uploaded document ID
    """

    # Upload document using the client
    response = client.upload_document(token=token, file_content=file_content, filename=filename, check_fields=check_fields)

    return UploadDocumentResponse(document_id=response.id, filename=filename, check_fields=check_fields)


def _get_full_document(client: SignNowAPIClient, token: str, document_id: str, document_data: DocumentResponse) -> DocumentGroupDocument:
    """
    Get full document information including field values.

    This function retrieves a document with all its metadata and field values.
    The basic information (id, name, roles) comes from the document endpoint,
    while field values are retrieved separately using get_document_fields.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_id: ID of the document to retrieve
        document_data: Pre-fetched document data to avoid duplicate API calls

    Returns:
        DocumentGroupDocument with complete document information including field values
    """

    # Use provided document data
    document_response = document_data

    # Create DocumentField objects with values
    document_fields = []

    for field in document_response.fields:
        if field.type == "text":
            document_fields.append(
                DocumentField(
                    id=field.id,
                    type=field.type,
                    role_id=field.role,  # Using role name as role_id for consistency
                    value=field.json_attributes.prefilled_text or "",
                    name=field.json_attributes.name,
                )
            )

    return DocumentGroupDocument(id=document_response.id, name=document_response.document_name, roles=[role.name for role in document_response.roles], fields=document_fields)


def _get_full_document_group(client: SignNowAPIClient, token: str, group_data: GetDocumentGroupV2Response) -> DocumentGroup:
    """
    Get full document group information including all documents with their field values.

    This function retrieves a document group using v2 API and for each document in the group,
    gets the complete document information including field values.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_group_id: ID of the document group to retrieve
        group_data: Pre-fetched group data to avoid duplicate API calls

    Returns:
        DocumentGroup with complete information including all documents with field values
    """

    # Use provided group data
    group_data = group_data.data

    # Get full document information for each document in the group
    full_documents = []
    for doc in group_data.documents:
        # Get document data first
        document_data = client.get_document(token, doc.id)
        full_doc = _get_full_document(client=client, token=token, document_id=doc.id, document_data=document_data)
        full_documents.append(full_doc)

    # Create DocumentGroup with full document information
    return DocumentGroup(
        last_updated=group_data.created,  # Use created timestamp as last_updated
        entity_id=group_data.id,
        group_name=group_data.name,
        entity_type="document_group",
        invite_id=group_data.invite_id,
        invite_status=group_data.state,  # Use state as invite_status
        documents=full_documents,
    )


def _get_document(client: SignNowAPIClient, token: str, entity_id: str, entity_type: Literal["document", "document_group"] | None = None) -> DocumentGroup:
    """
    Get document or document group information with full field values.

    This function determines the entity type if not provided and returns
    a DocumentGroup with complete information including field values.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        entity_id: ID of the document or document group
        entity_type: Type of entity: 'document' or 'document_group' (optional)

    Returns:
        DocumentGroup with complete information including field values

    Raises:
        ValueError: If entity not found as either document or document group
    """

    # Determine entity type if not provided and get entity data
    document_data = None
    group_data = None

    if not entity_type:
        # Try to determine entity type by attempting to get document first
        try:
            # Try to get document - if successful, it's a document
            document_data = client.get_document(token, entity_id)
            entity_type = "document"
        except:
            # If document not found, try document group
            try:
                # Try to get document group - if successful, it's a document group
                group_data = client.get_document_group_v2(token, entity_id)
                entity_type = "document_group"
            except:
                raise ValueError(f"Entity with ID {entity_id} not found as either document or document group")
    else:
        # Entity type is provided, get the entity data
        if entity_type == "document_group":
            group_data = client.get_document_group_v2(token, entity_id)
        else:  # entity_type == "document"
            document_data = client.get_document(token, entity_id)

    # Get the appropriate data based on determined or provided entity type
    if entity_type == "document_group":
        return _get_full_document_group(client, token, group_data)
    else:  # entity_type == "document"
        return _get_single_document_as_group(client, token, entity_id, document_data)


def _get_single_document_as_group(client: SignNowAPIClient, token: str, document_id: str, document_data: DocumentResponse) -> DocumentGroup:
    """
    Get a single document and return it as a DocumentGroup with one document.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        document_id: ID of the document to retrieve
        document_data: Pre-fetched document data to avoid duplicate API calls

    Returns:
        DocumentGroup containing the single document with full field values
    """

    # Get full document information
    full_document = _get_full_document(client, token, document_id, document_data)

    # Create DocumentGroup with single document
    return DocumentGroup(
        last_updated=0,  # Not available for single documents
        entity_id=document_id,
        group_name=full_document.name,
        entity_type="document",
        invite_id=None,  # Not available for single documents
        invite_status=None,  # Not available for single documents
        documents=[full_document],
    )


def _update_document_fields(client: SignNowAPIClient, token: str, update_requests: list[UpdateDocumentFields]) -> UpdateDocumentFieldsResponse:
    """
    Update fields for multiple documents.

    This function updates text fields in multiple documents using the SignNow API.
    Only text fields can be updated using the prefill_text_fields endpoint.

    Args:
        client: SignNow API client instance
        token: Access token for authentication
        update_requests: List of UpdateDocumentFields with document IDs and fields to update

    Returns:
        UpdateDocumentFieldsResponse with results for each document update
    """

    results = []

    for update_request in update_requests:
        try:
            # Convert FieldToUpdate to PrefillTextField format
            prefill_fields = []
            for field in update_request.fields:
                prefill_fields.append({"field_name": field.name, "prefilled_text": field.value})

            # Create PrefillTextFieldsRequest
            from signnow_client.models.templates_and_documents import (
                PrefillTextField,
                PrefillTextFieldsRequest,
            )

            prefill_request = PrefillTextFieldsRequest(fields=[PrefillTextField(field_name=field.name, prefilled_text=field.value) for field in update_request.fields])

            # Update fields using the client
            success = client.prefill_text_fields(token=token, document_id=update_request.document_id, request_data=prefill_request)

            results.append(UpdateDocumentFieldsResult(document_id=update_request.document_id, updated=success, reason=None))  # No reason needed for success

        except Exception as e:
            # Log error and mark as failed
            error_message = str(e)
            print(f"Failed to update fields for document {update_request.document_id}: {error_message}")
            results.append(UpdateDocumentFieldsResult(document_id=update_request.document_id, updated=False, reason=error_message))

    return UpdateDocumentFieldsResponse(results=results)
