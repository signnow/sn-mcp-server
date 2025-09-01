"""
SignNow API Client - Base Class

Base client class with common HTTP methods and error handling.
"""

import httpx
import json
from typing import Optional, Dict, Any
from .config import SignNowConfig
from .exceptions import (
    SignNowAPIError,
    SignNowAPITimeoutError,
    SignNowAPIHTTPError,
    SignNowAPIAuthenticationError,
    SignNowAPINotFoundError,
    SignNowAPIRateLimitError,
    SignNowAPIServerError
)


class SignNowAPIClientBase:
    """Base client class with common HTTP methods and error handling"""
    
    def __init__(self, cfg: SignNowConfig, client: httpx.Client | None = None):
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
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close client"""
        self.close()
    
    def close(self):
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
        error_message = "Unknown error"
        if isinstance(response_data, dict):
            error_message = response_data.get("error", response_data.get("message", str(e)))
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
    
    def _get(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None, validate_model=None) -> Any:
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
            raise self._handle_http_error(e)
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in GET request to {url}: {e}") from e
    
    def _post(self, url: str, headers: Optional[Dict[str, str]] = None, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, validate_model=None) -> Any:
        """Internal POST method with unified error handling and optional model validation"""
        try:
            response = self.http.post(url, headers=headers, data=data, json=json_data)
            response.raise_for_status()
            data = response.json()
            
            # Validate with model if provided
            if validate_model:
                return validate_model.model_validate(data)
            return data
        except httpx.TimeoutException as e:
            raise SignNowAPITimeoutError("SignNow API timeout") from e
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e)
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in POST request to {url}: {e}") from e
    
    def _put(self, url: str, headers: Optional[Dict[str, str]] = None, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, validate_model=None) -> Any:
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
            raise self._handle_http_error(e)
        except json.JSONDecodeError as e:
            raise SignNowAPIError(f"Error parsing SignNow API response: {e}") from e
        except Exception as e:
            raise SignNowAPIError(f"Unexpected error in PUT request to {url}: {e}") from e 