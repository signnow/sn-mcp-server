"""
SignNow Client Utilities

Utility functions and helpers for the SignNow API client.
"""

import base64
from typing import Any


def encode_basic_auth(client_id: str, client_secret: str) -> str:
    """
    Encode client_id:client_secret as Basic Auth token

    Args:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret

    Returns:
        Base64 encoded Basic Auth token
    """
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode()


def decode_basic_auth(basic_token: str) -> tuple[str, str]:
    """
    Decode Basic Auth token to client_id and client_secret

    Args:
        basic_token: Base64 encoded Basic Auth token

    Returns:
        Tuple of (client_id, client_secret)
    """
    try:
        decoded = base64.b64decode(basic_token.encode()).decode()
        client_id, client_secret = decoded.split(":", 1)
        return client_id, client_secret
    except Exception:
        raise ValueError("Invalid Basic Auth token format")


def validate_token_response(response_data: dict[str, Any]) -> bool:
    """
    Validate that a token response contains required fields

    Args:
        response_data: Response data from token endpoint

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["access_token", "token_type"]
    return all(field in response_data for field in required_fields)
