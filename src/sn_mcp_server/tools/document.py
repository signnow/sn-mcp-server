"""
Upload Document Tool

Tool for uploading documents to SignNow.
"""

from typing import Optional
from signnow_client import SignNowAPIClient
from .models import UploadDocumentResponse


def _upload_document(
    file_content: bytes,
    filename: str,
    check_fields: bool,
    token: str,
    client: SignNowAPIClient
) -> UploadDocumentResponse:
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
    response = client.upload_document(
        token=token,
        file_content=file_content,
        filename=filename,
        check_fields=check_fields
    )
    
    return UploadDocumentResponse(
        document_id=response.id,
        filename=filename,
        check_fields=check_fields
    )
