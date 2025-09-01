"""
SignNow API Client Package

This package provides a client for interacting with the SignNow API,
including OAuth2 authentication and token management.
"""

from .client import SignNowAPIClient
from .config import SignNowConfig, load_signnow_config
from .utils import encode_basic_auth, decode_basic_auth, validate_token_response
from .models import (
    Thumbnail,
    Template,
    DocumentGroupTemplate,
    DocumentGroupTemplatesResponse,
    CreateDocumentGroupFromTemplateRequest,
    CreateDocumentFromTemplateRequest,
    CreateFieldInviteRequest,
    FieldInviteStep,
    FieldInviteAction,
    FieldInviteEmail,
    CreateDocumentFieldInviteRequest,
    DocumentFieldInviteRecipient,
)
from .exceptions import (
    SignNowAPIError,
    SignNowAPITimeoutError,
    SignNowAPIHTTPError,
    SignNowAPIAuthenticationError,
    SignNowAPINotFoundError,
    SignNowAPIRateLimitError,
    SignNowAPIServerError
)

__all__ = [
    'SignNowAPIClient', 
    'SignNowConfig', 
    'load_signnow_config',
    'encode_basic_auth', 
    'decode_basic_auth', 
    'validate_token_response',
    'Thumbnail',
    'Template',
    'DocumentGroupTemplate',
    'DocumentGroupTemplatesResponse',
    'CreateDocumentGroupFromTemplateRequest',
    'CreateDocumentFromTemplateRequest',
    'CreateFieldInviteRequest',
    'FieldInviteStep',
    'FieldInviteAction',
    'FieldInviteEmail',
    'CreateDocumentFieldInviteRequest',
    'DocumentFieldInviteRecipient',
    'SignNowAPIError',
    'SignNowAPITimeoutError',
    'SignNowAPIHTTPError',
    'SignNowAPIAuthenticationError',
    'SignNowAPINotFoundError',
    'SignNowAPIRateLimitError',
    'SignNowAPIServerError'
]
__version__ = '1.0.0'
