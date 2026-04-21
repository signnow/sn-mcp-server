"""
SignNow API Client - Other Methods

Methods for authentication, folders, and other utilities.
"""

import json
from typing import Any

from signnow_client.models.contacts import CrmContactsResponse
from signnow_client.models.folders_lite import GetFolderByIdResponseLite, GetFoldersResponseLite

from .client_base import SignNowAPIClientBase
from .models import User


class OtherClientMixin(SignNowAPIClientBase):
    """Mixin class for other client methods like authentication and folders"""

    def get_tokens(self, code: str) -> dict[str, Any] | None:
        """
        Get access and refresh tokens from SignNow API using authorization code

        Args:
            code: Authorization code from OAuth2 flow

        Returns:
            Dictionary with tokens or None if failed
        """
        result: dict[str, Any] | None = self._post(
            "/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "scope": "*",
                "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return result

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any] | None:
        """
        Get new tokens from SignNow API using refresh token

        Args:
            refresh_token: Refresh token to use

        Returns:
            Dictionary with new tokens or None if failed
        """
        result: dict[str, Any] | None = self._post(
            "/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return result

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token using SignNow API

        Args:
            token: Access token to revoke

        Returns:
            True if successful (2xx including 204 No Content), False otherwise. Raises on network/timeout errors.
        """
        response = self.http.post(
            "/oauth2/terminate",
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={},
        )
        return response.is_success

    def get_tokens_by_password(self, username: str, password: str, scope: str | None = None) -> dict[str, Any] | None:
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
        if not basic_auth:
            # SignNowConfig.validate_one_of_credentials requires basic_token whenever the
            # password grant is chosen, so this path should be unreachable in configured
            # deployments. Raise an explicit error rather than sending a broken header.
            raise ValueError("SIGNNOW_API_BASIC_TOKEN must be set to use the password grant")

        result: dict[str, Any] | None = self._post(
            "/oauth2/token",
            headers={"Accept": "application/json", "Authorization": "Basic " + basic_auth, "Content-Type": "application/x-www-form-urlencoded"},
            data={"username": username, "password": password, "grant_type": "password", "scope": scope},
        )
        return result

    def get_folders(self, token: str, entity_type: str | None = None) -> GetFoldersResponseLite:
        """
        Get all folders of a user.

        This endpoint returns all folders of a user including system folders like
        Templates, Team Templates, Archive, Trash Bin, and Documents.

        Args:
            token: Access token for authentication
            entity_type: Defines what entities should be in the response
                        Possible values: 'document-all', 'all', 'document', 'document-group', 'dgt', 'template'

        Returns:
            Validated GetFoldersResponseLite model with complete folder structure
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        params = {"with_team_documents": "true"}

        if entity_type:
            params["entity_type"] = entity_type

        return self._get("/user/folder", headers=headers, params=params, validate_model=GetFoldersResponseLite)

    def get_folder_by_id(
        self,
        token: str,
        folder_id: str,
        filters: str | None = None,
        filter_values: str | None = None,
        sortby: str | None = None,
        order: str = "desc",
        offset: int | None = None,
        limit: int | None = None,
        entity_type: str = "document-all",
        entity_labels: str | None = None,
        include_documents_subfolders: bool | None = None,
        with_team_documents: bool | None = None,
        only_favorites: bool = False,
    ) -> GetFolderByIdResponseLite:
        """
        Get folder by ID with detailed information.

        This endpoint returns all details of a specific folder including an array
        of all documents in that folder. The response can be customized using
        various query parameters for filtering, sorting, and pagination.

        Args:
            token: Access token for authentication
            folder_id: ID of the folder to retrieve
            filters: Filter documents by status, created date, or updated date
                    Possible values: 'signing-status', 'documents-created', 'documents-updated'
            filter_values: Values for the filters parameter
                         For signing-status: 'signed', 'pending', 'waiting-for-me', 'waiting-for-others', 'unsent', 'expired'
                         For dates: UNIX timestamp
            sortby: Sort by created date, updated date, or document name
                   Possible values: 'updated', 'created', 'document-name'
            order: Order of sorting (asc/desc), default: desc
            offset: Display documents from this position
            limit: Maximum number of documents to return (max: 100)
            entity_type: Defines what entities should be in the response
                        Possible values: 'document-all', 'all', 'document', 'document-group', 'dgt', 'template'
            entity_labels: Filter by labels like 'declined', 'undelivered'
            include_documents_subfolders: Whether to include subfolders
            with_team_documents: Whether to display Team Documents folders
            only_favorites: Show only favorite documents and document groups

        Returns:
            Validated GetFolderByIdResponseLite model with folder details and documents
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        params: dict[str, Any] = {}

        if filters:
            params["filters"] = filters
        if filter_values:
            params["filter-values"] = filter_values
        if sortby:
            params["sortby"] = sortby
        if order:
            params["order"] = order
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if entity_type:
            params["entity_type"] = entity_type
        if entity_labels:
            params["entity_labels"] = entity_labels
        if include_documents_subfolders is not None:
            params["include_documents_subfolders"] = 1 if include_documents_subfolders else 0
        if with_team_documents is not None:
            params["with_team_documents"] = with_team_documents
        if only_favorites:
            params["only_favorites"] = only_favorites

        return self._get(f"/folder/{folder_id}", headers=headers, params=params, validate_model=GetFolderByIdResponseLite)

    def get_user_info(self, token: str) -> User:
        """
        Get user information from SignNow API.

        This endpoint returns comprehensive user information including:
        - Basic user details (name, email, etc.)
        - Subscription information
        - Billing details
        - Team and organization information
        - User settings and preferences
        - Document counts and statistics

        Args:
            token: Access token for authentication

        Returns:
            Validated User model with complete user information
        """

        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}

        return self._get("/user", headers=headers, validate_model=User)

    def get_contacts(
        self,
        token: str,
        query: str | None = None,
        per_page: int = 15,
    ) -> CrmContactsResponse:
        """Retrieve CRM contacts from SignNow.

        Calls GET /v2/crm/contacts. When ``query`` is provided, serializes
        a JSON ``filters`` parameter using the ``_OR`` combinator so the API
        performs a LIKE match against email, first_name, last_name, full_name,
        and phone simultaneously.

        Filter JSON shape (from API docs)::

            filters=[{"_OR":[
                {"email":     {"type": "like", "value": "query"}},
                {"first_name":{"type": "like", "value": "query"}},
                {"last_name": {"type": "like", "value": "query"}},
                {"full_name": {"type": "like", "value": "query"}},
                {"phone":     {"type": "like", "value": "query"}}
            ]}]

        Args:
            token: Access token for authentication.
            query: Optional search string to filter contacts by name, email, or phone.
            per_page: Number of contacts to return per page (1–100, default 15).

        Returns:
            Validated CrmContactsResponse with list of contacts.

        Raises:
            SignNowAPIAuthenticationError: Invalid or expired token.
            SignNowAPIRateLimitError: Rate limit exceeded.
            SignNowAPIServerError: SignNow backend error.
        """
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        params: dict[str, str | int] = {"per_page": per_page, "page": 1}

        stripped_query = (query or "").strip()
        if stripped_query:
            params["filters"] = json.dumps([
                {
                    "_OR": [
                        {"email": {"type": "like", "value": stripped_query}},
                        {"first_name": {"type": "like", "value": stripped_query}},
                        {"last_name": {"type": "like", "value": stripped_query}},
                        {"full_name": {"type": "like", "value": stripped_query}},
                        {"phone": {"type": "like", "value": stripped_query}},
                    ]
                }
            ])

        return self._get("/v2/crm/contacts", headers=headers, params=params, validate_model=CrmContactsResponse)
