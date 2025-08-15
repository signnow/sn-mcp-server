"""
SignNow API Client

Main client class for interacting with the SignNow API.
"""

import httpx
from typing import Optional, Dict, Any
from .config import SignNowConfig, load_signnow_config
from .models import DocumentGroupTemplatesResponse, DocumentGroupsResponse
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
    
    def get_tokens(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get access and refresh tokens from SignNow API using authorization code
        
        Args:
            code: Authorization code from OAuth2 flow
            
        Returns:
            Dictionary with tokens or None if failed
        """
        try:
            response = self.http.post(
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
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"SignNow API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error calling SignNow API: {e}")
            return None
    
    def refresh_tokens(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Get new tokens from SignNow API using refresh token
        
        Args:
            refresh_token: Refresh token to use
            
        Returns:
            Dictionary with new tokens or None if failed
        """
        try:
            response = self.http.post(
                "/oauth2/token",
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.cfg.client_id,
                    'client_secret': self.cfg.client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"SignNow API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error refreshing token with SignNow API: {e}")
            return None
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token using SignNow API
        
        Args:
            token: Access token to revoke
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.http.post(
                "/oauth2/terminate",
                headers={
                    'Accept': 'application/json',
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json={}
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"SignNow API revoke error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Error calling SignNow revoke API: {e}")
            return False
    
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
        try:
            scope = scope or self.cfg.default_scope
            basic_auth = self.cfg.basic_token

            response = self.http.post(
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
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"SignNow API password grant error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error calling SignNow API with password grant: {e}")
            return None

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

        try:
            response = self.http.get("/user/documentgroup/templates", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Validate and return the response as a model
            return DocumentGroupTemplatesResponse.model_validate(data)
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Error getting templates: {str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing response: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error validating response: {str(e)}")

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

        try:
            response = self.http.get("/user/documentgroups", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Validate and return the response as a model
            return DocumentGroupsResponse.model_validate(data)
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Error getting document groups: {str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing response: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error validating response: {str(e)}")