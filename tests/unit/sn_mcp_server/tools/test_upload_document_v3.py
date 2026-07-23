"""Unit tests for the v3.0 upload_document tool boundary (signnow_v3.py).

These cover the tool-layer contract that the shared ``_upload_document`` helper
tests don't: the agent-facing ``kind`` selector must map to ``make_template`` on
the client call — ``kind='template'`` → ``True``, the default ``'document'`` →
``False``. The tool's async body is captured by intercepting ``@mcp.tool`` during
``bind`` (the same pattern as test_tool_versions.py), then awaited with the token,
client, and resource resolution patched out.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from typing import Protocol, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sn_mcp_server.tools import signnow_v3
from sn_mcp_server.tools.models import UploadDocumentResponse

FAKE_TOKEN = "fake-token"  # noqa: S105


class _UploadTool(Protocol):
    """Call signature of the captured v3 upload_document coroutine."""

    def __call__(
        self,
        *,
        ctx: object,
        resource_uri: str | None = ...,
        file_path: str | None = ...,
        file_url: str | None = ...,
        filename: str | None = ...,
        kind: str = ...,
    ) -> Awaitable[UploadDocumentResponse]: ...


class _CapturingMCP:
    """Fake FastMCP that records the function each ``@mcp.tool`` decorates."""

    def __init__(self) -> None:
        self.captured: dict[str, object] = {}

    def tool(self, **kwargs: object) -> Callable[[object], object]:
        name = str(kwargs["name"])

        def deco(fn: object) -> object:
            self.captured[name] = fn
            return fn

        return deco


class TestUploadDocumentV3Kind:
    """The v3 tool must translate ``kind`` into the client's ``make_template``."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.upload_document.return_value = MagicMock(id="tpl_1")
        return client

    @pytest.fixture
    def upload_tool(self, mock_client: MagicMock) -> Iterator[_UploadTool]:
        """Bind the v3 tools with token/client/resource resolution patched, yield upload_document."""
        mcp = _CapturingMCP()
        with (
            patch("sn_mcp_server.tools.signnow_v3.TokenProvider"),
            patch("sn_mcp_server.tools.signnow_v3._get_token_and_client", return_value=(FAKE_TOKEN, mock_client)),
            patch("sn_mcp_server.tools.signnow_v3._resolve_upload_resource", new=AsyncMock(return_value=(b"pdf bytes", "contract.pdf"))),
        ):
            signnow_v3.bind(mcp, object())
            yield cast(_UploadTool, mcp.captured["upload_document"])

    async def test_kind_template_maps_make_template_true(self, upload_tool: _UploadTool, mock_client: MagicMock) -> None:
        """kind='template' forwards make_template=True and returns template follow-ups."""
        result = await upload_tool(ctx=AsyncMock(), resource_uri="file:///docs/contract.pdf", kind="template")

        assert mock_client.upload_document.call_args.kwargs["make_template"] is True
        assert result.document_id == "tpl_1"
        assert result.source == "resource"
        assert [step.tool for step in result.next_steps] == ["create_from_template", "create_embedded_editor"]

    async def test_default_kind_maps_make_template_false(self, upload_tool: _UploadTool, mock_client: MagicMock) -> None:
        """Omitting kind defaults to 'document', forwarding make_template=False and document follow-ups."""
        result = await upload_tool(ctx=AsyncMock(), resource_uri="file:///docs/contract.pdf")

        assert mock_client.upload_document.call_args.kwargs["make_template"] is False
        assert result.source == "resource"
        assert [step.tool for step in result.next_steps] == ["create_embedded_sending", "send_invite", "send_invite"]

    async def test_explicit_kind_document_maps_make_template_false(self, upload_tool: _UploadTool, mock_client: MagicMock) -> None:
        """kind='document' behaves identically to the default."""
        await upload_tool(ctx=AsyncMock(), resource_uri="file:///docs/contract.pdf", kind="document")

        assert mock_client.upload_document.call_args.kwargs["make_template"] is False
