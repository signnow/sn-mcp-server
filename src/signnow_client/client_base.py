"""
SignNow API Client - Base Class

Base client class with common HTTP methods and error handling.
"""

import json
from types import TracebackType
from typing import Any, TypeVar, overload

import httpx
from pydantic import BaseModel

from .config import SignNowConfig
from .exceptions import (
    SignNowAPIAuthenticationError,
    SignNowAPIError,
    SignNowAPIHTTPError,
    SignNowAPINotFoundError,
    SignNowAPIRateLimitError,
    SignNowAPIServerError,
    SignNowAPITimeoutError,
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class SignNowAPIClientBase:
    """Base client class with common HTTP methods and error handling"""

    def __init__(self, cfg: SignNowConfig, client: httpx.Client | None = None) -> None:
        """
        Initialize the SignNow API client

        Args:
            cfg: Configuration object
            client: Optional httpx client. If not provided, creates a default one.
        """
        self.cfg = cfg
        self.http = client or httpx.Client(
            base_url=str(cfg.api_base),
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={"User-Agent": "sn-mcp-server/0.1"},
        )

    def __enter__(self) -> "SignNowAPIClientBase":
        """Context manager entry"""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - close client"""
        self.close()

    def close(self) -> None:
        """Close the httpx client"""
        if self.http:
            self.http.close()

    def _handle_http_error(self, e: httpx.HTTPStatusError) -> SignNowAPIError:
        """Convert httpx HTTPStatusError to appropriate SignNow API error"""
        status_code = e.response.status_code
        response_data = {}

        try:
            response_data = e.response.json()
        except (json.JSONDecodeError, ValueError):
            response_data = {"text": e.response.text}

        # Extract error message from response if available
        error_message: str = "Unknown error"
        if isinstance(response_data, dict):
            error_msg = response_data.get("error", response_data.get("message", str(e)))
            if error_msg is not None:
                error_message = str(error_msg)
        else:
            error_message = str(e)

        # Map status codes to specific exception types
        if status_code in (401, 403):
            return SignNowAPIAuthenticationError(error_message, status_code, response_data)
        elif status_code == 404:
            return SignNowAPINotFoundError(error_message, status_code, response_data)
        elif status_code == 429:
            return SignNowAPIRateLimitError(error_message, status_code, response_data)
        elif status_code >= 500:
            return SignNowAPIServerError(error_message, status_code, response_data)
        else:
            return SignNowAPIHTTPError(error_message, status_code, response_data)

    @overload
    def _get(self, url: str, headers: dict[str, str] | None = ..., params: dict[str, Any] | None = ..., *, validate_model: type[_ModelT]) -> _ModelT: ...
    @overload
    def _get(self, url: str, headers: dict[str, str] | None = ..., params: dict[str, Any] | None = ..., validate_model: None = None) -> Any: ...  # noqa: ANN401
    def _get(self, url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, validate_model: type[BaseModel] | None = None) -> Any:  # noqa: ANN401
        """Internal GET method with unified error handling and optional model validation"""
        try:
            response = self.http.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            # Validate with model if provided
            if validate_model:
                return validate_model.model_validate(data)
            return data
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in GET request to {url}: {e}") from e

    @overload
    def _post(self, url: str, headers: dict[str, str] | None = ..., data: dict[str, Any] | None = ..., json_data: dict[str, Any] | None = ..., *, validate_model: type[_ModelT]) -> _ModelT: ...
    @overload
    def _post(self, url: str, headers: dict[str, str] | None = ..., data: dict[str, Any] | None = ..., json_data: dict[str, Any] | None = ..., validate_model: None = None) -> Any: ...  # noqa: ANN401
    def _post(self, url: str, headers: dict[str, str] | None = None, data: dict[str, Any] | None = None, json_data: dict[str, Any] | None = None, validate_model: type[BaseModel] | None = None) -> Any:  # noqa: ANN401
        """Internal POST method with unified error handling and optional model validation"""
        try:
            response = self.http.post(url, headers=headers, data=data, json=json_data)
            response.raise_for_status()

            # 204 No Content or empty body (e.g. 202 Accepted) — nothing to parse
            if response.status_code == 204 or not response.content.strip():
                return None

            data = response.json()

            # Validate with model if provided
            if validate_model:
                return validate_model.model_validate(data)
            return data
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in POST request to {url}: {e}") from e

    @overload
    def _put(self, url: str, headers: dict[str, str] | None = ..., data: dict[str, Any] | None = ..., json_data: dict[str, Any] | None = ..., *, validate_model: type[_ModelT]) -> _ModelT: ...
    @overload
    def _put(self, url: str, headers: dict[str, str] | None = ..., data: dict[str, Any] | None = ..., json_data: dict[str, Any] | None = ..., validate_model: None = None) -> Any: ...  # noqa: ANN401
    def _put(self, url: str, headers: dict[str, str] | None = None, data: dict[str, Any] | None = None, json_data: dict[str, Any] | None = None, validate_model: type[BaseModel] | None = None) -> Any:  # noqa: ANN401
        """Internal PUT method with unified error handling and optional model validation"""
        try:
            response = self.http.put(url, headers=headers, data=data, json=json_data)
            response.raise_for_status()
            data = response.json()

            # Validate with model if provided
            if validate_model:
                return validate_model.model_validate(data)
            return data
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in PUT request to {url}: {e}") from e

    @overload
    def _post_multipart(self, url: str, headers: dict[str, str] | None = ..., files: dict[str, Any] | None = ..., data: dict[str, Any] | None = ..., *, validate_model: type[_ModelT]) -> _ModelT: ...
    @overload
    def _post_multipart(self, url: str, headers: dict[str, str] | None = ..., files: dict[str, Any] | None = ..., data: dict[str, Any] | None = ..., validate_model: None = None) -> Any: ...  # noqa: ANN401
    def _post_multipart(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        validate_model: type[BaseModel] | None = None,
    ) -> Any:  # noqa: ANN401
        """Internal POST method with multipart form data and unified error handling"""
        try:
            response = self.http.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            data = response.json()

            # Validate with model if provided
            if validate_model:
                return validate_model.model_validate(data)
            return data
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in POST multipart request to {url}: {e}") from e

    @overload
    def _delete(self, url: str, headers: dict[str, str] | None = ..., *, validate_model: type[_ModelT]) -> _ModelT: ...
    @overload
    def _delete(self, url: str, headers: dict[str, str] | None = ..., validate_model: None = None) -> Any: ...  # noqa: ANN401
    def _delete(self, url: str, headers: dict[str, str] | None = None, validate_model: type[BaseModel] | None = None) -> Any:  # noqa: ANN401
        """Internal DELETE method with unified error handling and optional model validation"""
        try:
            response = self.http.delete(url, headers=headers)
            response.raise_for_status()

            if response.status_code == 204 or not response.content.strip():
                return None

            data = response.json()

            if validate_model:
                return validate_model.model_validate(data)
            return data
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e) from e
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in DELETE request to {url}: {e}") from e
