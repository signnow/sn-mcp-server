"""Unit tests for signnow_v1 — v1.0 backward-compatible tool wrappers."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sn_mcp_server.tools.models import (
    EmbeddedInviteOrder,
    EmbeddedInviteRecipient,
    InviteOrder,
    InviteRecipient,
)
from sn_mcp_server.tools.models_v1 import (
    CreateEmbeddedEditorResponseV1,
    CreateEmbeddedInviteFromTemplateResponse,
    CreateEmbeddedInviteResponseV1,
    CreateEmbeddedSendingResponseV1,
    SendInviteFromTemplateResponse,
    SendInviteResponseV1,
)
from sn_mcp_server.tools.signnow_v1 import _parse_embedded_orders, _parse_invite_orders

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_invite_order(email: str = "signer@example.com", role: str = "Signer", order: int = 1) -> InviteOrder:
    return InviteOrder(order=order, recipients=[InviteRecipient(email=email, role=role, action="sign", redirect_uri=None)])


def _make_embedded_order(email: str = "signer@example.com", role: str = "Signer", order: int = 1) -> EmbeddedInviteOrder:
    return EmbeddedInviteOrder(order=order, recipients=[EmbeddedInviteRecipient(email=email, role=role, action="sign")])


def _capture_v1_tools() -> dict[str, Any]:
    """Register v1 tools and return {tool_name: async_fn} mapping."""
    from fastmcp import FastMCP

    from sn_mcp_server.tools import signnow_v1

    mcp: Any = FastMCP("v1-test")
    captured: dict[str, Any] = {}
    original_tool = mcp.tool

    def recording_tool(*args: Any, **kwargs: Any) -> Any:
        decorator = original_tool(*args, **kwargs)
        name: str = kwargs.get("name", "")
        version: str = kwargs.get("version", "")

        def wrap(fn: Any) -> Any:
            if version == "1.0":
                key = f"{name}@{version}"
                captured[key] = fn
            return decorator(fn)

        return wrap

    mcp.tool = recording_tool
    signnow_v1.bind(mcp, None)
    return captured


_V1_TOOLS = _capture_v1_tools()


# ──────────────────────────────────────────────────────────────────────────────
# _parse_invite_orders
# ──────────────────────────────────────────────────────────────────────────────


class TestParseInviteOrders:
    """Tests for _parse_invite_orders helper."""

    def test_none_returns_empty_list(self) -> None:
        result = _parse_invite_orders(None)
        assert result == []

    def test_list_passthrough(self) -> None:
        orders = [_make_invite_order()]
        result = _parse_invite_orders(orders)
        assert result == orders

    def test_valid_json_string_parsed(self) -> None:
        orders_json = json.dumps([{"order": 1, "recipients": [{"email": "a@b.com", "role": "Signer", "action": "sign", "redirect_uri": None}]}])
        result = _parse_invite_orders(orders_json)
        assert len(result) == 1
        assert isinstance(result[0], InviteOrder)
        assert result[0].recipients[0].email == "a@b.com"

    def test_invalid_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid orders JSON string"):
            _parse_invite_orders("{not valid json")

    def test_invalid_schema_raises_value_error(self) -> None:
        # Valid JSON but wrong schema (missing 'order' key)
        with pytest.raises(Exception):  # noqa: B017
            _parse_invite_orders(json.dumps([{"recipients": []}]))


# ──────────────────────────────────────────────────────────────────────────────
# _parse_embedded_orders
# ──────────────────────────────────────────────────────────────────────────────


class TestParseEmbeddedOrders:
    """Tests for _parse_embedded_orders helper."""

    def test_none_returns_empty_list(self) -> None:
        result = _parse_embedded_orders(None)
        assert result == []

    def test_list_passthrough(self) -> None:
        orders = [_make_embedded_order()]
        result = _parse_embedded_orders(orders)
        assert result == orders

    def test_valid_json_string_parsed(self) -> None:
        orders_json = json.dumps([{"order": 1, "recipients": [{"email": "a@b.com", "role": "Signer", "action": "sign"}]}])
        result = _parse_embedded_orders(orders_json)
        assert len(result) == 1
        assert isinstance(result[0], EmbeddedInviteOrder)
        assert result[0].recipients[0].email == "a@b.com"

    def test_invalid_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid orders JSON string"):
            _parse_embedded_orders("not json")

    def test_invalid_schema_raises_exception(self) -> None:
        """Valid JSON but wrong schema (missing required 'order' key) raises."""
        with pytest.raises(Exception):  # noqa: B017
            _parse_embedded_orders(json.dumps([{"recipients": []}]))


# ──────────────────────────────────────────────────────────────────────────────
# send_invite v1.0
# ──────────────────────────────────────────────────────────────────────────────


class TestSendInviteV1:
    """Tests for send_invite v1.0 wrapper."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_v1_shape(self, mock_ctx: MagicMock) -> None:
        """send_invite v1.0 returns SendInviteResponseV1 without created_entity_* fields."""
        from sn_mcp_server.tools.models import SendInviteResponse

        v2_response = SendInviteResponse(invite_id="inv_1", invite_entity="document", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._send_invite", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["send_invite@1.0"]
                result = await fn(mock_ctx, entity_id="doc1", orders=[_make_invite_order()])

        assert isinstance(result, SendInviteResponseV1)
        assert result.invite_id == "inv_1"
        assert result.invite_entity == "document"
        assert not hasattr(result, "created_entity_id")

    async def test_accepts_json_string_orders(self, mock_ctx: MagicMock) -> None:
        """send_invite v1.0 accepts orders as a JSON string."""
        from sn_mcp_server.tools.models import SendInviteResponse

        v2_response = SendInviteResponse(invite_id="inv_1", invite_entity="document", created_entity_id=None, created_entity_type=None, created_entity_name=None)
        orders_json = json.dumps([{"order": 1, "recipients": [{"email": "a@b.com", "role": "Signer", "action": "sign", "redirect_uri": None}]}])

        call_args: list[Any] = []

        async def capture_send(*args: Any, **kwargs: Any) -> Any:
            call_args.extend(args)
            return v2_response

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._send_invite", new=capture_send):
                fn = _V1_TOOLS["send_invite@1.0"]
                await fn(mock_ctx, entity_id="doc1", orders=orders_json)

        # Third positional arg to _send_invite is the parsed orders list
        assert isinstance(call_args[2], list)
        assert isinstance(call_args[2][0], InviteOrder)

    async def test_empty_orders_raises(self, mock_ctx: MagicMock) -> None:
        """send_invite v1.0 raises ValueError when orders is None or empty."""
        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            fn = _V1_TOOLS["send_invite@1.0"]
            with pytest.raises(ValueError, match="orders must contain at least one"):
                await fn(mock_ctx, entity_id="doc1", orders=None)


# ──────────────────────────────────────────────────────────────────────────────
# create_embedded_invite v1.0
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateEmbeddedInviteV1:
    """Tests for create_embedded_invite v1.0 wrapper."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_v1_shape_for_document_group(self, mock_ctx: MagicMock) -> None:
        """create_embedded_invite v1.0 maps document_group_invite_id → invite_id."""
        from sn_mcp_server.tools.models import CreateEmbeddedInviteResponse

        v2_response = CreateEmbeddedInviteResponse(
            document_group_invite_id="grp_inv_1",
            invite_entity="document_group",
            recipient_links=[],
            created_entity_id=None,
            created_entity_type=None,
            created_entity_name=None,
        )

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_invite", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["create_embedded_invite@1.0"]
                result = await fn(mock_ctx, entity_id="grp1", orders=[_make_embedded_order()])

        assert isinstance(result, CreateEmbeddedInviteResponseV1)
        assert result.invite_id == "grp_inv_1"
        assert result.invite_entity == "document_group"

    async def test_returns_v1_shape_for_document(self, mock_ctx: MagicMock) -> None:
        """create_embedded_invite v1.0 extracts document_invite_id from recipient_links."""
        from sn_mcp_server.tools.models import CreateEmbeddedInviteResponse

        v2_response = CreateEmbeddedInviteResponse(
            document_group_invite_id=None,
            invite_entity="document",
            recipient_links=[{"role": "Signer", "link": "https://link", "document_invite_id": "doc_inv_1"}],
            created_entity_id=None,
            created_entity_type=None,
            created_entity_name=None,
        )

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_invite", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["create_embedded_invite@1.0"]
                result = await fn(mock_ctx, entity_id="doc1", orders=[_make_embedded_order()])

        assert isinstance(result, CreateEmbeddedInviteResponseV1)
        assert result.invite_id == "doc_inv_1"
        assert result.invite_entity == "document"
        assert len(result.recipient_links) == 1


# ──────────────────────────────────────────────────────────────────────────────
# create_embedded_sending v1.0
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateEmbeddedSendingV1:
    """Tests for create_embedded_sending v1.0 wrapper."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_v1_shape(self, mock_ctx: MagicMock) -> None:
        """create_embedded_sending v1.0 returns shape without created_entity_* fields."""
        from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse

        v2_response = CreateEmbeddedSendingResponse(sending_entity="document", sending_url="https://app.signnow.com/send/1", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_sending", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["create_embedded_sending@1.0"]
                result = await fn(mock_ctx, entity_id="doc1")

        assert isinstance(result, CreateEmbeddedSendingResponseV1)
        assert result.sending_url == "https://app.signnow.com/send/1"
        assert not hasattr(result, "created_entity_id")

    async def test_link_expiration_days_passed_as_is(self, mock_ctx: MagicMock) -> None:
        """link_expiration (days 14-45) is passed as-is to business logic."""
        from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse

        v2_response = CreateEmbeddedSendingResponse(sending_entity="document", sending_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)
        captured_kwargs: dict[str, Any] = {}

        async def capture_sending(*args: Any, **kwargs: Any) -> Any:
            # link_expiration_minutes is positional arg[4] in _create_embedded_sending
            captured_kwargs["link_expiration_minutes"] = args[4] if len(args) > 4 else kwargs.get("link_expiration_minutes")
            return v2_response

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_sending", new=capture_sending):
                fn = _V1_TOOLS["create_embedded_sending@1.0"]
                await fn(mock_ctx, entity_id="doc1", link_expiration=30)

        assert captured_kwargs["link_expiration_minutes"] == 30

    async def test_link_expiration_max_45_accepted(self, mock_ctx: MagicMock) -> None:
        """link_expiration=45 (v1 max) is accepted without ValidationError."""
        from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse

        v2_response = CreateEmbeddedSendingResponse(sending_entity="document", sending_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)
        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_sending", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["create_embedded_sending@1.0"]
                result = await fn(mock_ctx, entity_id="doc1", link_expiration=45)
        assert result.sending_url == "https://test"


# ──────────────────────────────────────────────────────────────────────────────
# create_embedded_editor v1.0
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateEmbeddedEditorV1:
    """Tests for create_embedded_editor v1.0 wrapper."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_v1_shape(self, mock_ctx: MagicMock) -> None:
        """create_embedded_editor v1.0 returns shape without created_entity_* fields."""
        from sn_mcp_server.tools.models import CreateEmbeddedEditorResponse

        v2_response = CreateEmbeddedEditorResponse(editor_entity="document", editor_url="https://app.signnow.com/edit/1", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_editor", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["create_embedded_editor@1.0"]
                result = await fn(mock_ctx, entity_id="doc1")

        assert isinstance(result, CreateEmbeddedEditorResponseV1)
        assert result.editor_url == "https://app.signnow.com/edit/1"
        assert not hasattr(result, "created_entity_id")

    async def test_link_expiration_max_45_accepted(self, mock_ctx: MagicMock) -> None:
        """link_expiration=45 (v1 max, minutes) is accepted; 46 should fail pydantic."""
        from sn_mcp_server.tools.models import CreateEmbeddedEditorResponse

        v2_response = CreateEmbeddedEditorResponse(editor_entity="document", editor_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_embedded_editor", new=AsyncMock(return_value=v2_response)):
                fn = _V1_TOOLS["create_embedded_editor@1.0"]
                result = await fn(mock_ctx, entity_id="doc1", link_expiration=45)
        assert result.editor_url == "https://test"


# ──────────────────────────────────────────────────────────────────────────────
# send_invite_from_template v1.0 (compound)
# ──────────────────────────────────────────────────────────────────────────────


class TestSendInviteFromTemplateV1:
    """Tests for send_invite_from_template v1.0 compound tool."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_correct_response(self, mock_ctx: MagicMock) -> None:
        """send_invite_from_template v1.0 returns SendInviteFromTemplateResponse with all expected fields."""
        from sn_mcp_server.tools.models import CreateFromTemplateResponse, SendInviteResponse

        created = CreateFromTemplateResponse(entity_id="new_doc", entity_type="document", name="New Doc")
        invite = SendInviteResponse(invite_id="inv_1", invite_entity="document", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._send_invite", new=AsyncMock(return_value=invite)):
                    fn = _V1_TOOLS["send_invite_from_template@1.0"]
                    result = await fn(mock_ctx, entity_id="tmpl1", orders=[_make_invite_order()])

        assert isinstance(result, SendInviteFromTemplateResponse)
        assert result.created_entity_id == "new_doc"
        assert result.created_entity_type == "document"
        assert result.created_entity_name == "New Doc"
        assert result.invite_id == "inv_1"
        assert result.invite_entity == "document"

    async def test_progress_reported_three_times(self, mock_ctx: MagicMock) -> None:
        """send_invite_from_template v1.0 reports 3 progress steps."""
        from sn_mcp_server.tools.models import CreateFromTemplateResponse, SendInviteResponse

        created = CreateFromTemplateResponse(entity_id="doc1", entity_type="document", name="Doc")
        invite = SendInviteResponse(invite_id="inv_1", invite_entity="document", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._send_invite", new=AsyncMock(return_value=invite)):
                    fn = _V1_TOOLS["send_invite_from_template@1.0"]
                    await fn(mock_ctx, entity_id="tmpl1", orders=[_make_invite_order()])

        assert mock_ctx.report_progress.call_count == 3


# ──────────────────────────────────────────────────────────────────────────────
# create_embedded_invite_from_template v1.0 (compound)
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateEmbeddedInviteFromTemplateV1:
    """Tests for create_embedded_invite_from_template v1.0 compound tool."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_correct_response(self, mock_ctx: MagicMock) -> None:
        """create_embedded_invite_from_template v1.0 returns correct response shape."""
        from sn_mcp_server.tools.models import CreateEmbeddedInviteResponse, CreateFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="new_grp", entity_type="document_group", name="New Group")
        invite = CreateEmbeddedInviteResponse(
            document_group_invite_id="grp_inv_1",
            invite_entity="document_group",
            recipient_links=[{"role": "Signer", "link": "https://link"}],
            created_entity_id=None,
            created_entity_type=None,
            created_entity_name=None,
        )

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_invite", new=AsyncMock(return_value=invite)):
                    fn = _V1_TOOLS["create_embedded_invite_from_template@1.0"]
                    result = await fn(mock_ctx, entity_id="tmpl1", orders=[_make_embedded_order()])

        assert isinstance(result, CreateEmbeddedInviteFromTemplateResponse)
        assert result.created_entity_id == "new_grp"
        assert result.invite_id == "grp_inv_1"
        assert result.invite_entity == "document_group"
        assert len(result.recipient_links) == 1


# ──────────────────────────────────────────────────────────────────────────────
# create_embedded_sending_from_template v1.0 (compound)
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateEmbeddedSendingFromTemplateV1:
    """Tests for create_embedded_sending_from_template v1.0 compound tool."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock Context with report_progress."""
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_correct_response(self, mock_ctx: MagicMock) -> None:
        """create_embedded_sending_from_template v1.0 returns correct response shape."""
        from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse, CreateFromTemplateResponse
        from sn_mcp_server.tools.models_v1 import CreateEmbeddedSendingFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="new_doc", entity_type="document", name="New Doc")
        sending = CreateEmbeddedSendingResponse(
            sending_entity="document",
            sending_url="https://app.signnow.com/send/abc",
            created_entity_id=None,
            created_entity_type=None,
            created_entity_name=None,
        )

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_sending", new=AsyncMock(return_value=sending)):
                    fn = _V1_TOOLS["create_embedded_sending_from_template@1.0"]
                    result = await fn(mock_ctx, entity_id="tmpl1")

        assert isinstance(result, CreateEmbeddedSendingFromTemplateResponse)
        assert result.created_entity_id == "new_doc"
        assert result.created_entity_type == "document"
        assert result.created_entity_name == "New Doc"
        assert result.sending_entity == "document"
        assert result.sending_url == "https://app.signnow.com/send/abc"

    async def test_link_expiration_passed_as_is(self, mock_ctx: MagicMock) -> None:
        """link_expiration (days) is forwarded as-is to link_expiration_minutes param."""
        from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse, CreateFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="doc1", entity_type="document", name="Doc")
        sending = CreateEmbeddedSendingResponse(sending_entity="document", sending_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)
        captured: dict[str, Any] = {}

        async def capture_sending(*args: Any, **kwargs: Any) -> Any:
            # link_expiration_minutes is positional arg[4]
            captured["link_expiration_minutes"] = args[4] if len(args) > 4 else kwargs.get("link_expiration_minutes")
            return sending

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_sending", new=capture_sending):
                    fn = _V1_TOOLS["create_embedded_sending_from_template@1.0"]
                    await fn(mock_ctx, entity_id="tmpl1", link_expiration=28)

        assert captured["link_expiration_minutes"] == 28

    async def test_progress_reported_three_times(self, mock_ctx: MagicMock) -> None:
        """create_embedded_sending_from_template v1.0 reports 3 progress steps."""
        from sn_mcp_server.tools.models import CreateEmbeddedSendingResponse, CreateFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="doc1", entity_type="document", name="Doc")
        sending = CreateEmbeddedSendingResponse(sending_entity="document", sending_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_sending", new=AsyncMock(return_value=sending)):
                    fn = _V1_TOOLS["create_embedded_sending_from_template@1.0"]
                    await fn(mock_ctx, entity_id="tmpl1")

        assert mock_ctx.report_progress.call_count == 3


# ──────────────────────────────────────────────────────────────────────────────
# create_embedded_editor_from_template v1.0 (compound)
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateEmbeddedEditorFromTemplateV1:
    """Tests for create_embedded_editor_from_template v1.0 compound tool."""

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock Context with report_progress."""
        ctx = MagicMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_returns_correct_response(self, mock_ctx: MagicMock) -> None:
        """create_embedded_editor_from_template v1.0 returns correct response shape."""
        from sn_mcp_server.tools.models import CreateEmbeddedEditorResponse, CreateFromTemplateResponse
        from sn_mcp_server.tools.models_v1 import CreateEmbeddedEditorFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="new_doc", entity_type="document", name="New Doc")
        editor = CreateEmbeddedEditorResponse(
            editor_entity="document",
            editor_url="https://app.signnow.com/edit/abc",
            created_entity_id=None,
            created_entity_type=None,
            created_entity_name=None,
        )

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_editor", new=AsyncMock(return_value=editor)):
                    fn = _V1_TOOLS["create_embedded_editor_from_template@1.0"]
                    result = await fn(mock_ctx, entity_id="tmpl1")

        assert isinstance(result, CreateEmbeddedEditorFromTemplateResponse)
        assert result.created_entity_id == "new_doc"
        assert result.created_entity_type == "document"
        assert result.created_entity_name == "New Doc"
        assert result.editor_entity == "document"
        assert result.editor_url == "https://app.signnow.com/edit/abc"

    async def test_link_expiration_max_45_accepted(self, mock_ctx: MagicMock) -> None:
        """link_expiration=45 (v1 max, minutes) is accepted without error."""
        from sn_mcp_server.tools.models import CreateEmbeddedEditorResponse, CreateFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="doc1", entity_type="document", name="Doc")
        editor = CreateEmbeddedEditorResponse(editor_entity="document", editor_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_editor", new=AsyncMock(return_value=editor)):
                    fn = _V1_TOOLS["create_embedded_editor_from_template@1.0"]
                    result = await fn(mock_ctx, entity_id="tmpl1", link_expiration=45)

        assert result.editor_url == "https://test"

    async def test_progress_reported_three_times(self, mock_ctx: MagicMock) -> None:
        """create_embedded_editor_from_template v1.0 reports 3 progress steps."""
        from sn_mcp_server.tools.models import CreateEmbeddedEditorResponse, CreateFromTemplateResponse

        created = CreateFromTemplateResponse(entity_id="doc1", entity_type="document", name="Doc")
        editor = CreateEmbeddedEditorResponse(editor_entity="document", editor_url="https://test", created_entity_id=None, created_entity_type=None, created_entity_name=None)

        with patch("sn_mcp_server.tools.signnow_v1._get_token_and_client", return_value=("tok", MagicMock())):
            with patch("sn_mcp_server.tools.signnow_v1._create_from_template", return_value=created):
                with patch("sn_mcp_server.tools.signnow_v1._create_embedded_editor", new=AsyncMock(return_value=editor)):
                    fn = _V1_TOOLS["create_embedded_editor_from_template@1.0"]
                    await fn(mock_ctx, entity_id="tmpl1")

        assert mock_ctx.report_progress.call_count == 3
