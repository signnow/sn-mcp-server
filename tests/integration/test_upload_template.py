"""
Integration tests for _upload_template — tool function wired to real SignNowAPIClient.

HTTP layer is mocked via respx; no real network calls.
Tests validate the full flow: tool function → SignNowAPIClient → HTTP construction → response parsing.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
import respx

from signnow_client import SignNowAPIClient
from signnow_client.exceptions import SignNowAPIHTTPError
from sn_mcp_server.tools.document import _upload_template
from sn_mcp_server.tools.models import UploadTemplateResponse


class TestUploadTemplateIntegration:
    """Integration tests for _upload_template."""

    async def test_upload_resource_integration(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """resource_bytes → POST /document (make_template) → 200 → correct UploadTemplateResponse."""
        # ARRANGE
        route = mock_api.post("/document").respond(200, json={"id": "sn_res_tpl"})

        # ACT
        result = _upload_template(
            client=sn_client,
            token=token,
            resource_bytes=b"fake pdf",
            filename="tpl.pdf",
        )

        # ASSERT
        assert route.called
        body = route.calls.last.request.content.decode("latin-1")
        assert "make_template" in body
        assert isinstance(result, UploadTemplateResponse)
        assert result.template_id == "sn_res_tpl"
        assert result.source == "resource"

    async def test_upload_local_file_integration(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
        tmp_path: pathlib.Path,
    ) -> None:
        """file_path → POST /document (make_template) → 200 → correct UploadTemplateResponse."""
        # ARRANGE
        fixture = load_fixture("post_upload_document__success")
        route = mock_api.post("/document").respond(200, json=fixture)

        tmp_file = tmp_path / "blueprint.pdf"
        tmp_file.write_bytes(b"pdf content")

        # ACT — patch SAFE_UPLOAD_BASE to allow tmp_path (outside real home)
        with patch("sn_mcp_server.tools.document.SAFE_UPLOAD_BASE", tmp_path):
            result = _upload_template(
                client=sn_client,
                token=token,
                file_path=str(tmp_file),
            )

        # ASSERT
        assert route.called
        assert result.template_id == fixture["id"]
        assert result.source == "local_file"

    async def test_upload_url_integration(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        """file_url → POST /v2/documents/url (make_template) → 200 → correct UploadTemplateResponse."""
        # ARRANGE
        fixture = load_fixture("post_create_document_from_url__success")
        route = mock_api.post("/v2/documents/url").respond(200, json=fixture)

        # ACT
        result = _upload_template(
            client=sn_client,
            token=token,
            file_url="https://example.com/nda.pdf",
        )

        # ASSERT
        assert route.called
        body = json.loads(route.calls.last.request.content)
        assert body["make_template"] is True
        # Inferred filename must NOT be transmitted — only an explicit filename becomes the name.
        assert "name" not in body
        assert result.template_id == fixture["id"]
        assert result.source == "url"

    async def test_upload_api_error_integration(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
    ) -> None:
        """POST /document → 400 → SignNowAPIHTTPError raised."""
        # ARRANGE
        mock_api.post("/document").respond(400, json={"errors": [{"code": 0, "message": "bad file"}]})

        # ACT & ASSERT
        with pytest.raises(SignNowAPIHTTPError):
            _upload_template(
                client=sn_client,
                token=token,
                resource_bytes=b"bad",
                filename="bad.pdf",
            )
