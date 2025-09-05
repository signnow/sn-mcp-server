"""
SignNow API Exceptions

Custom exception classes for SignNow API errors.
"""

from typing import Any


class SignNowAPIError(Exception):
    """Base exception for SignNow API errors"""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"SignNow API Error {self.status_code}: {self.message}"
        return f"SignNow API Error: {self.message}"


class SignNowAPITimeoutError(SignNowAPIError):
    """Exception raised when SignNow API request times out"""

    def __init__(self, message: str = "SignNow API request timed out"):
        super().__init__(message)


class SignNowAPIHTTPError(SignNowAPIError):
    """Exception raised when SignNow API returns an HTTP error status"""

    def __init__(self, message: str, status_code: int, response_data: dict[str, Any] | None = None):
        super().__init__(message, status_code, response_data)
        self.status_code = status_code

    def __str__(self) -> str:
        base_message = f"SignNow API HTTP Error {self.status_code}: {self.message}"
        if self.response_data:
            return f"{base_message}\nResponse body: {self.response_data}"
        return base_message


class SignNowAPIAuthenticationError(SignNowAPIHTTPError):
    """Exception raised when SignNow API authentication fails (401, 403)"""

    def __init__(self, message: str = "SignNow API authentication failed", status_code: int = 401, response_data: dict[str, Any] | None = None):
        super().__init__(message, status_code, response_data)


class SignNowAPINotFoundError(SignNowAPIHTTPError):
    """Exception raised when SignNow API resource is not found (404)"""

    def __init__(self, message: str = "SignNow API resource not found", status_code: int = 404, response_data: dict[str, Any] | None = None):
        super().__init__(message, status_code, response_data)


class SignNowAPIRateLimitError(SignNowAPIHTTPError):
    """Exception raised when SignNow API rate limit is exceeded (429)"""

    def __init__(self, message: str = "SignNow API rate limit exceeded", status_code: int = 429, response_data: dict[str, Any] | None = None):
        super().__init__(message, status_code, response_data)


class SignNowAPIServerError(SignNowAPIHTTPError):
    """Exception raised when SignNow API server error occurs (5xx)"""

    def __init__(self, message: str = "SignNow API server error", status_code: int = 500, response_data: dict[str, Any] | None = None):
        super().__init__(message, status_code, response_data)
