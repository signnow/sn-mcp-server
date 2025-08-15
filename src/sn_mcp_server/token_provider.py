from typing import Optional, Dict, Any
from .config import load_settings
from signnow_client import SignNowAPIClient
from signnow_client.config import load_signnow_config

class TokenProvider:
    """Automatically provides access tokens from config credentials or authorization headers"""
    
    def __init__(self):
        self.settings = load_settings()
        self.signnow_config = load_signnow_config()
        self.signnow_client = SignNowAPIClient(self.signnow_config)
    
    def get_access_token(self, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Get access token either from config credentials or from request headers
        
        Args:
            headers: Optional request headers dictionary
            
        Returns:
            Access token string or None if unable to get token
        """
        # First try to get token from config credentials
        if self.has_config_credentials():
            return self._get_token_from_config()
        
        # If no config credentials, try to extract from headers
        if headers:
            return self._extract_token_from_headers(headers)
        
        return None
    
    def has_config_credentials(self) -> bool:
        """Check if username and password are configured"""
        return bool(self.signnow_config.user_email and self.signnow_config.password and self.signnow_config.basic_token)
    
    def _get_token_from_config(self) -> Optional[str]:
        """Get token using configured username and password"""
        try:
            # Get new token from SignNow API
            response = self.signnow_client.get_tokens_by_password(
                username=self.signnow_config.user_email,
                password=self.signnow_config.password
            )
            
            if response and "access_token" in response:
                return response["access_token"]
            
            return None
            
        except Exception as e:
            print(f"Error getting token from config: {e}")
            return None
    
    def _extract_token_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """Extract token from request headers, checking multiple possible locations"""
        if not headers:
            return None
        
        # Try authorization header first
        auth_header = headers.get('authorization', '')
        if auth_header:
            # Remove 'Bearer ' prefix if present
            if auth_header.startswith("Bearer "):
                return auth_header[7:]  # Remove 'Bearer ' prefix
            return auth_header
        
        # Try other common header names
        for header_name in ['x-access-token', 'x-auth-token', 'token']:
            token = headers.get(header_name, '')
            if token:
                return token
        
        return None 