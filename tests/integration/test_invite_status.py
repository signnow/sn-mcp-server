"""
Integration tests for _get_invite_status — tool layer through SignNowAPIClient with respx.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import respx

from signnow_client import SignNowAPIClient
from sn_mcp_server.tools.invite_status import _get_invite_status
from sn_mcp_server.tools.models import InviteStatus


class TestInviteStatusDocumentFreeform:
    """Document with no field_invites — GET v2/.../free-form-invites."""

    def test_end_to_end(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        doc_fixture = load_fixture("get_document__no_field_invites")
        mock_api.get("/document/doc_ff_int").respond(200, json=doc_fixture)
        mock_api.get("/v2/documents/doc_ff_int/free-form-invites").respond(
            200,
            json={
                "data": [
                    {
                        "id": "ff_row_1",
                        "status": "pending",
                        "created": 1700000000,
                        "email": "int_test@example.com",
                    }
                ],
                "meta": {},
            },
        )

        result = _get_invite_status("doc_ff_int", "document", token, sn_client)

        assert isinstance(result, InviteStatus)
        assert result.invite_mode == "freeform"
        assert result.invite_id == "ff_row_1"
        assert result.steps[0].actions[0].email == "int_test@example.com"


class TestInviteStatusDocumentGroupFreeform:
    """Group with freeform_invite — GET v2/.../documents for signature_requests."""

    def test_end_to_end(
        self,
        sn_client: SignNowAPIClient,
        mock_api: respx.MockRouter,
        token: str,
        load_fixture: Callable[[str], dict[str, Any]],
    ) -> None:
        group_fixture = load_fixture("get_document_group_v2__freeform_invite")
        mock_api.get("/v2/document-groups/grp_ff_int").respond(200, json=group_fixture)
        mock_api.get("/v2/document-groups/grp_ff_int/documents").respond(
            200,
            json={
                "data": [
                    {
                        "id": "doc_a",
                        "signature_requests": [
                            {
                                "user_id": "u1",
                                "status": "pending",
                                "email": "one@example.com",
                            }
                        ],
                    }
                ],
                "meta": {},
            },
        )

        result = _get_invite_status("grp_ff_int", "document_group", token, sn_client)

        assert result.invite_mode == "freeform"
        assert result.invite_id == "ff_grp_1"
        assert result.steps[0].actions[0].email == "one@example.com"
        assert result.steps[0].actions[0].document_id == "doc_a"
