"""Unit tests for the shared MCP-resource upload helper in signnow.py.

`_resolve_upload_resource` backs the `resource_uri` branch of the
`upload_document` tool: it reads an attached MCP resource via
`ctx.read_resource`, validates it carries binary content, and infers a
filename from the URI when the caller didn't supply one.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sn_mcp_server.tools.signnow import _resolve_upload_resource


def _make_ctx(content: object, contents_empty: bool = False) -> AsyncMock:
    """Build an async Context whose read_resource returns the given content."""
    ctx = AsyncMock()
    result = MagicMock()
    result.contents = [] if contents_empty else [MagicMock(content=content)]
    ctx.read_resource.return_value = result
    return ctx


class TestResolveUploadResource:
    """Direct tests for the _resolve_upload_resource helper."""

    async def test_none_resource_uri_is_noop(self) -> None:
        """When resource_uri is None the helper returns (None, filename) unchanged."""
        ctx = AsyncMock()
        resource_bytes, filename = await _resolve_upload_resource(ctx, None, "given.pdf")
        assert resource_bytes is None
        assert filename == "given.pdf"
        ctx.read_resource.assert_not_called()

    async def test_reads_bytes_and_infers_filename(self) -> None:
        """A binary resource yields its bytes and a filename inferred from the URI."""
        ctx = _make_ctx(b"pdf bytes")
        resource_bytes, filename = await _resolve_upload_resource(ctx, "file:///docs/contract.pdf", None)
        assert resource_bytes == b"pdf bytes"
        assert filename == "contract.pdf"
        ctx.read_resource.assert_awaited_once_with("file:///docs/contract.pdf")

    async def test_explicit_filename_preserved(self) -> None:
        """An explicit filename is kept and not overwritten by URI inference."""
        ctx = _make_ctx(b"pdf bytes")
        resource_bytes, filename = await _resolve_upload_resource(ctx, "file:///docs/contract.pdf", "override.pdf")
        assert resource_bytes == b"pdf bytes"
        assert filename == "override.pdf"

    @pytest.mark.parametrize("empty_uri", ["", "   "])
    async def test_empty_resource_uri_raises(self, empty_uri: str) -> None:
        """Empty/whitespace resource_uri raises before any read."""
        ctx = AsyncMock()
        with pytest.raises(ValueError, match="resource_uri must not be empty"):
            await _resolve_upload_resource(ctx, empty_uri, None)
        ctx.read_resource.assert_not_called()

    async def test_empty_contents_raises(self) -> None:
        """A resource returning no content raises ValueError."""
        ctx = _make_ctx(None, contents_empty=True)
        with pytest.raises(ValueError, match="returned no content"):
            await _resolve_upload_resource(ctx, "file:///docs/contract.pdf", None)

    async def test_text_content_raises(self) -> None:
        """A resource returning text rather than bytes raises ValueError."""
        ctx = _make_ctx("not bytes")
        with pytest.raises(ValueError, match="returned text, expected binary"):
            await _resolve_upload_resource(ctx, "file:///docs/contract.pdf", None)

    async def test_uninferable_filename_raises(self) -> None:
        """When no filename is given and none can be inferred from the URI, it raises."""
        ctx = _make_ctx(b"pdf bytes")
        with pytest.raises(ValueError, match="Cannot infer filename"):
            await _resolve_upload_resource(ctx, "custom://server", None)
