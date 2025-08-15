"""
SignNow API Client

Main client class for interacting with the SignNow API.
"""

import httpx
from typing import Optional, Dict, Any
from .config import SignNowConfig, load_signnow_config
from .models import DocumentGroupTemplatesResponse, DocumentGroupsResponse
from .exceptions import (
    SignNowAPIError,
    SignNowAPITimeoutError,
    SignNowAPIHTTPError,
    SignNowAPIAuthenticationError,
    SignNowAPINotFoundError,
    SignNowAPIRateLimitError,
    SignNowAPIServerError
)
import json


class SignNowAPIClient:
    """Client for interacting with SignNow API"""
    
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
            http2=True,
            timeout=httpx.Timeout(10.0, connect=3.0),
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
    
    def get_tokens(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get access and refresh tokens from SignNow API using authorization code
        
        Args:
            code: Authorization code from OAuth2 flow
            
        Returns:
            Dictionary with tokens or None if failed
        """
        return self._post(
            "/oauth2/token",
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'scope': '*',
                'client_id': self.cfg.client_id,
                'client_secret': self.cfg.client_secret,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
    
    def refresh_tokens(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Get new tokens from SignNow API using refresh token
        
        Args:
            refresh_token: Refresh token to use
            
        Returns:
            Dictionary with new tokens or None if failed
        """
        return self._post(
            "/oauth2/token",
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.cfg.client_id,
                'client_secret': self.cfg.client_secret,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token using SignNow API
        
        Args:
            token: Access token to revoke
            
        Returns:
            True if successful, False otherwise
        """
        self._post(
            "/oauth2/terminate",
            headers={
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            json_data={}
        )
        return True
    
    def get_tokens_by_password(self, username: str, password: str, scope: str = None) -> Optional[Dict[str, Any]]:
        """
        Get access and refresh tokens from SignNow API using username and password 
        (Resource Owner Password Credentials grant)
        
        Args:
            username: User's email/username
            password: User's password
            scope: OAuth scope (defaults to configured default scope)
            
        Returns:
            Dictionary with tokens or None if failed
        """
        scope = scope or self.cfg.default_scope
        basic_auth = self.cfg.basic_token

        return self._post(
            "/oauth2/token",
            headers={
                'Accept': 'application/json',
                'Authorization': 'Basic ' + basic_auth,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={
                'username': username,
                'password': password,
                'grant_type': 'password',
                'scope': scope
            }
        )

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
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        params = {"limit": limit, "offset": offset}

        return self._get(
            "/user/documentgroup/templates", 
            headers=headers, 
            params=params,
            validate_model=DocumentGroupTemplatesResponse
        )

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
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        params = {"limit": limit, "offset": offset}

        return self._get(
            "/user/documentgroups", 
            headers=headers, 
            params=params,
            validate_model=DocumentGroupsResponse
        )