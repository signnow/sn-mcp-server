"""Full SignNow workflow scenario — the one E2E scenario shipped with this harness.

Happy path: send_invite on a pre-seeded document → get_invite_status →
get_document_download_link. The scenario hands the agent a specific
document id in the prompt and a clear objective; all SignNow HTTP traffic
is intercepted by respx and replied to with pydantic-valid fixtures so
tool calls actually succeed.

Mirrors ``mcp/eval/scenarios/full-session.ts`` from the TypeScript
auto-cources harness, adapted to the SignNow tool surface.
"""

from __future__ import annotations

import os
from typing import Any

import respx
from httpx import Response

from ..types import (
    Invariant,
    InvariantEnv,
    ScenarioDefinition,
    ScenarioFixture,
)

_FAKE_API_BASE = "https://api-eval.signnow.com"
_DOC_ID = "doc_eval_001"


def build_full_flow_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        name="full-flow",
        summary=("One document, one recipient, one invite. Every phase of the core invite → status → download tool chain must be exercised."),
        initial_prompt=(
            "You are assisting a SignNow user. They want to send document "
            f"'{_DOC_ID}' (it is a regular document, not a template or group) "
            "to recipient@example.com for signature, then check that the "
            "invite was delivered, and finally fetch a download link for the "
            "signed copy. Use the SignNow MCP tools to carry this out. Always "
            "pass entity_type='document' so auto-detection is skipped. Keep "
            "your messages very short — one sentence between tool calls is "
            "enough. Do not lecture; act via tools."
        ),
        simulated_learner_replies=[
            "Yes, please proceed.",
            "That looks right. Continue.",
            "Thanks, that's everything.",
        ],
        invariants=[invite_used_expected_doc_id],
        seed=_seed,
        read_env=_read_env,
    )


async def _seed() -> ScenarioFixture:
    """Set env, start respx, register routes for the happy path."""
    # Env must be set before create_server() reads it.
    os.environ["SIGNNOW_API_BASE"] = _FAKE_API_BASE
    os.environ["SIGNNOW_USER_EMAIL"] = "eval@example.com"
    os.environ["SIGNNOW_PASSWORD"] = "eval-password"  # noqa: S105
    os.environ["SIGNNOW_API_BASIC_TOKEN"] = "eval-basic-token"  # noqa: S105

    # respx patches httpx globally. We pin SignNow routes by absolute URL and
    # finish with a catch-all `.pass_through()` so non-SignNow traffic (the
    # LiteLLM proxy, direct Anthropic/OpenAI) reaches the real network. We
    # deliberately DO NOT pass `base_url=_FAKE_API_BASE` to `respx.mock()` —
    # that scopes the catch-all to the SignNow host too, breaking the drivers.
    router = respx.mock(assert_all_called=False)
    router.start()

    # OAuth — TokenProvider calls get_tokens_by_password on every tool invocation.
    router.post(f"{_FAKE_API_BASE}/oauth2/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "fake-eval-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "fake-refresh",
                "scope": "*",
            },
        )
    )

    # Auto-detection probes — for defence in depth when the agent omits entity_type.
    router.get(f"{_FAKE_API_BASE}/documentgroup/{_DOC_ID}").mock(return_value=Response(404, json={"error": "not found"}))
    router.get(f"{_FAKE_API_BASE}/v2/document-groups/{_DOC_ID}").mock(return_value=Response(404, json={"error": "not found"}))
    router.get(f"{_FAKE_API_BASE}/documentgroup/template/{_DOC_ID}").mock(return_value=Response(404, json={"error": "not found"}))

    # Document fetch — used by get_invite_status and by auto-detect fallback.
    router.get(f"{_FAKE_API_BASE}/document/{_DOC_ID}").mock(return_value=Response(200, json=_document_payload()))

    # send_invite (document path) calls get_user_info then POSTs /document/{id}/invite.
    router.get(f"{_FAKE_API_BASE}/user").mock(return_value=Response(200, json=_user_info_payload()))
    router.post(f"{_FAKE_API_BASE}/document/{_DOC_ID}/invite").mock(return_value=Response(200, json={"status": "sent", "id": "invite_eval_001"}))

    # Download link.
    router.post(f"{_FAKE_API_BASE}/document/{_DOC_ID}/download/link").mock(
        return_value=Response(
            200,
            json={"link": f"https://cdn-eval.signnow.com/files/{_DOC_ID}.pdf?token=xyz"},
        )
    )

    # Everything else (LiteLLM / direct Anthropic / direct OpenAI) falls
    # through to the real network. Must come AFTER the explicit routes —
    # respx matches routes in registration order.
    router.route().pass_through()

    return ScenarioFixture(
        facts={"doc_id": _DOC_ID, "router": router},
        teardown=_teardown_factory(router),
    )


def _teardown_factory(router: respx.MockRouter) -> Any:
    async def _teardown() -> None:
        router.stop()

    return _teardown


async def _read_env(fixture: ScenarioFixture) -> InvariantEnv:
    router: respx.MockRouter = fixture.facts["router"]
    requests: list[dict[str, Any]] = []
    for call in router.calls:
        requests.append({
            "method": call.request.method,
            "url": str(call.request.url),
            "path": call.request.url.path,
        })
    return InvariantEnv(
        mock_requests=requests,
        extra={"doc_id": fixture.facts["doc_id"]},
    )


def _send_invite_used_expected_doc(trace: Any, env: InvariantEnv) -> str | None:
    doc_id = env.extra.get("doc_id")
    invite_calls = [c for c in trace.tool_calls if c.tool == "send_invite"]
    if not invite_calls:
        return "send_invite was not called"
    args = invite_calls[0].args or {}
    if not isinstance(args, dict):
        return f"send_invite args were not a dict: {type(args).__name__}"
    seen = args.get("entity_id")
    if seen != doc_id:
        return f"send_invite entity_id={seen!r} does not match expected {doc_id!r}"
    return None


invite_used_expected_doc_id = Invariant(
    name="invite_used_expected_doc_id",
    rationale=(
        "The scenario prompt names a specific document id. If the agent invents "
        "its own id instead of reusing the one from the prompt, downstream tools "
        "look clean but the user's actual request was never honoured."
    ),
    check=_send_invite_used_expected_doc,
)


def _user_info_payload() -> dict[str, Any]:
    """Minimal valid GET /user response. Fields mirror the integration fixture."""
    return {
        "id": "user_eval_001",
        "first_name": "Eval",
        "last_name": "Owner",
        "active": "1",
        "type": 1,
        "pro": 0,
        "created": "1700000000",
        "emails": ["eval@example.com"],
        "primary_email": "eval@example.com",
        "credits": 0,
        "has_atticus_access": False,
        "cloud_export_account_details": None,
        "is_logged_in": True,
        "document_count": 0,
        "monthly_document_count": 0,
        "lifetime_document_count": 0,
        "googleapps": False,
        "facebookapps": False,
    }


def _document_payload() -> dict[str, Any]:
    """Minimal valid GET /document/{id} response with one pending invite."""
    return {
        "id": _DOC_ID,
        "user_id": "user_eval_001",
        "document_name": "Eval document",
        "page_count": "1",
        "created": "1700000000",
        "updated": "1700000100",
        "original_filename": "eval.pdf",
        "origin_document_id": None,
        "owner": "eval@example.com",
        "template": False,
        "thumbnail": {
            "small": "https://cdn-eval.signnow.com/small.png",
            "medium": "https://cdn-eval.signnow.com/medium.png",
            "large": "https://cdn-eval.signnow.com/large.png",
        },
        "signatures": [],
        "seals": [],
        "texts": [],
        "checks": [],
        "inserts": [],
        "tags": [],
        "fields": [],
        "requests": [],
        "notary_invites": [],
        "roles": [],
        "field_invites": [
            {
                "id": "fi_eval_001",
                "status": "pending",
                "created": "1700000000",
                "email": "recipient@example.com",
                "role": "Signer 1",
                "reminder": "0",
                "updated": "1700000100",
                "role_id": "r1",
                "declined": [],
            }
        ],
        "version_time": "1700000100",
        "enumeration_options": [],
        "attachments": [],
        "routing_details": [],
        "integrations": [],
        "hyperlinks": [],
        "radiobuttons": [],
        "document_group_template_info": [],
        "originator_organization_settings": [],
        "document_group_info": {},
        "parent_id": None,
        "originator_logo": "",
        "pages": [{"src": "https://cdn-eval.signnow.com/page1.png", "size": {"width": 612.0, "height": 792.0}}],
        "lines": [],
    }
