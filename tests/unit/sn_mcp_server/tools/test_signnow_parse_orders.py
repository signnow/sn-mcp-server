"""Unit tests for _normalize_order_field, _parse_orders, and _parse_embedded_orders in signnow.py."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from sn_mcp_server.tools.models import (
    EmbeddedInviteOrder,
    EmbeddedInviteRecipient,
    InviteOrder,
    InviteRecipient,
)
from sn_mcp_server.tools.signnow import (
    _normalize_order_field,
    _parse_embedded_orders,
    _parse_orders,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _invite_order(email: str = "signer@example.com", role: str = "Signer 1", order: int = 1) -> InviteOrder:
    return InviteOrder(order=order, recipients=[InviteRecipient(email=email, role=role)])


def _embedded_order(email: str = "signer@example.com", role: str = "Signer 1", order: int = 1) -> EmbeddedInviteOrder:
    return EmbeddedInviteOrder(order=order, recipients=[EmbeddedInviteRecipient(email=email, role=role)])


# ──────────────────────────────────────────────────────────────────────────────
# _normalize_order_field
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeOrderField:
    def test_adds_order_when_missing(self) -> None:
        raw = [{"recipients": [{"email": "a@b.com"}]}]
        _normalize_order_field(raw)
        assert raw[0]["order"] == 1

    def test_preserves_existing_order(self) -> None:
        raw = [{"order": 5, "recipients": [{"email": "a@b.com"}]}]
        _normalize_order_field(raw)
        assert raw[0]["order"] == 5

    def test_multiple_items_auto_numbered(self) -> None:
        raw = [{"recipients": []}, {"recipients": []}, {"recipients": []}]
        _normalize_order_field(raw)
        assert [item["order"] for item in raw] == [1, 2, 3]

    def test_mixed_present_and_missing(self) -> None:
        raw = [{"order": 10, "recipients": []}, {"recipients": []}]
        _normalize_order_field(raw)
        assert raw[0]["order"] == 10  # preserved
        assert raw[1]["order"] == 2  # filled from index

    def test_empty_list(self) -> None:
        raw: list = []
        _normalize_order_field(raw)
        assert raw == []

    def test_non_dict_items_skipped(self) -> None:
        """Non-dict items are left untouched (Pydantic will reject them later)."""
        raw: list = ["not a dict"]
        _normalize_order_field(raw)
        assert raw == ["not a dict"]

    def test_returns_same_list(self) -> None:
        raw = [{"recipients": []}]
        result = _normalize_order_field(raw)
        assert result is raw


# ──────────────────────────────────────────────────────────────────────────────
# _parse_orders
# ──────────────────────────────────────────────────────────────────────────────


class TestParseOrders:
    def test_none_returns_none(self) -> None:
        assert _parse_orders(None) is None

    def test_list_passthrough(self) -> None:
        orders = [_invite_order()]
        assert _parse_orders(orders) is orders

    def test_valid_json_string_with_order_field(self) -> None:
        data = [{"order": 1, "recipients": [{"email": "a@b.com", "role": "Signer 1"}]}]
        result = _parse_orders(json.dumps(data))
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], InviteOrder)
        assert result[0].order == 1
        assert result[0].recipients[0].email == "a@b.com"

    def test_json_string_without_order_field_auto_fills(self) -> None:
        """LLM sometimes omits 'order'; should be auto-filled from position."""
        data = [{"recipients": [{"email": "tymoshenko.anna@airslate.com", "role": "Recipient 1"}]}]
        result = _parse_orders(json.dumps(data))
        assert result is not None
        assert result[0].order == 1
        assert result[0].recipients[0].email == "tymoshenko.anna@airslate.com"

    def test_json_string_multiple_orders_auto_numbered(self) -> None:
        data = [
            {"recipients": [{"email": "a@a.com", "role": "R1"}]},
            {"recipients": [{"email": "b@b.com", "role": "R2"}]},
        ]
        result = _parse_orders(json.dumps(data))
        assert result is not None
        assert result[0].order == 1
        assert result[1].order == 2

    def test_invalid_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid orders JSON string"):
            _parse_orders("{bad json")

    def test_invalid_schema_raises(self) -> None:
        """Valid JSON but recipients field missing — Pydantic should reject."""
        with pytest.raises(ValidationError):
            _parse_orders(json.dumps([{"order": 1}]))

    def test_returns_typed_invite_order_instances(self) -> None:
        data = [{"recipients": [{"email": "x@x.com", "role": "Signer"}]}]
        result = _parse_orders(json.dumps(data))
        assert result is not None
        assert isinstance(result[0], InviteOrder)
        assert isinstance(result[0].recipients[0], InviteRecipient)


# ──────────────────────────────────────────────────────────────────────────────
# _parse_embedded_orders
# ──────────────────────────────────────────────────────────────────────────────


class TestParseEmbeddedOrders:
    def test_none_returns_none(self) -> None:
        assert _parse_embedded_orders(None) is None

    def test_list_passthrough(self) -> None:
        orders = [_embedded_order()]
        assert _parse_embedded_orders(orders) is orders

    def test_valid_json_string_with_order_field(self) -> None:
        data = [{"order": 1, "recipients": [{"email": "a@b.com", "role": "Signer 1", "action": "sign"}]}]
        result = _parse_embedded_orders(json.dumps(data))
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], EmbeddedInviteOrder)
        assert result[0].order == 1
        assert result[0].recipients[0].email == "a@b.com"

    def test_json_string_without_order_field_auto_fills(self) -> None:
        data = [{"recipients": [{"email": "e@e.com", "role": "Recipient 1"}]}]
        result = _parse_embedded_orders(json.dumps(data))
        assert result is not None
        assert result[0].order == 1
        assert result[0].recipients[0].email == "e@e.com"

    def test_json_string_multiple_orders_auto_numbered(self) -> None:
        data = [
            {"recipients": [{"email": "a@a.com", "role": "R1"}]},
            {"recipients": [{"email": "b@b.com", "role": "R2"}]},
        ]
        result = _parse_embedded_orders(json.dumps(data))
        assert result is not None
        assert result[0].order == 1
        assert result[1].order == 2

    def test_invalid_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid orders JSON string"):
            _parse_embedded_orders("not json at all")

    def test_invalid_schema_raises(self) -> None:
        with pytest.raises(ValidationError):
            _parse_embedded_orders(json.dumps([{"order": 1}]))

    def test_returns_typed_embedded_order_instances(self) -> None:
        data = [{"recipients": [{"email": "x@x.com", "role": "Signer"}]}]
        result = _parse_embedded_orders(json.dumps(data))
        assert result is not None
        assert isinstance(result[0], EmbeddedInviteOrder)
        assert isinstance(result[0].recipients[0], EmbeddedInviteRecipient)
