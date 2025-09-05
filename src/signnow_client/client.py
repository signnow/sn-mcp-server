"""
SignNow API Client

Main client class for interacting with the SignNow API.
"""

import httpx

from .client_base import SignNowAPIClientBase
from .client_document_groups import DocumentGroupClientMixin
from .client_documents import DocumentClientMixin
from .client_other import OtherClientMixin
from .config import SignNowConfig


class SignNowAPIClient(SignNowAPIClientBase, DocumentClientMixin, DocumentGroupClientMixin, OtherClientMixin):
    """
    Client for interacting with SignNow API

    This client combines methods from three categories:
    1. Document and Template methods (DocumentClientMixin)
    2. Document Groups and Template Groups methods (DocumentGroupClientMixin)
    3. Other methods like authentication and folders (OtherClientMixin)
    """

    def __init__(self, cfg: SignNowConfig, client: httpx.Client | None = None) -> None:
        """
        Initialize the SignNow API client

        Args:
            cfg: Configuration object
            client: Optional httpx client. If not provided, creates a default one.
        """
        super().__init__(cfg, client)
