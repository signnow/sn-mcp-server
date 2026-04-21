"""Two-agent flow scenario — LLM simulator drives the agent through a goal.

Unlike :mod:`eval.scenarios.full_flow`, the "user" side of this conversation
is played by a second Anthropic model with scripted goals and constraints
rather than a fixed list of canned replies. This catches regressions that
canned scripts can't: if the agent asks a clarifying question, a canned
"Continue." would let it sail past; a goal-driven simulator will push back
or answer coherently and keep steering toward completion.

Shares the respx seed shape with ``full_flow`` (same fake SignNow API,
same OAuth + document endpoints) but uses a different doc id so the two
scenarios don't collide in aggregated reports.

Mirrors the two-agent pattern from the TypeScript auto-cources harness.
"""

from __future__ import annotations

import os
from typing import Any

import respx
from httpx import Response

from ..simulators import LLMUserStrategy
from ..types import (
    Invariant,
    InvariantEnv,
    ScenarioDefinition,
    ScenarioFixture,
)

_FAKE_API_BASE = "https://api-eval.signnow.com"
_DOC_ID = "doc_eval_002"


def build_two_agent_flow_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        name="two-agent-flow",
        summary=(
            "Same invite → status → download chain as full-flow, but with an LLM simulator playing the user. Proves tool descriptions survive the extra ambiguity of a less-scripted conversation."
        ),
        initial_prompt=(
            "Hi, I need your help with a SignNow document. I'll tell you what I need step by step. Please use the SignNow MCP tools and keep your replies short — one sentence between actions."
        ),
        user=LLMUserStrategy(
            goal_steps=[
                (
                    f"Ask the assistant to send document '{_DOC_ID}' (it is a "
                    "regular document, not a template or group) to "
                    "client@example.com for signature. Insist on passing "
                    "entity_type='document' so auto-detection is skipped."
                ),
                "Once the invite is sent, ask the assistant to confirm it was delivered (invite status).",
                "Finally, ask for a download link for the signed copy.",
            ],
            constraints=[
                "Do not accept a preview or dry-run step — you want the invite actually sent.",
                f"The document id is '{_DOC_ID}'. If the assistant invents a different id, correct it.",
                "Never ask for anything unrelated to the three goals above.",
            ],
        ),
        invariants=[invite_used_expected_doc_id_two_agent],
        seed=_seed,
        read_env=_read_env,
    )


async def _seed() -> ScenarioFixture:
    """Set env, start respx, register routes for the happy path."""
    os.environ["SIGNNOW_API_BASE"] = _FAKE_API_BASE
    os.environ["SIGNNOW_USER_EMAIL"] = "eval@example.com"
    os.environ["SIGNNOW_PASSWORD"] = "eval-password"  # noqa: S105
    os.environ["SIGNNOW_API_BASIC_TOKEN"] = "eval-basic-token"  # noqa: S105

    router = respx.mock(assert_all_called=False)
    router.start()

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

    router.get(f"{_FAKE_API_BASE}/documentgroup/{_DOC_ID}").mock(return_value=Response(404, json={"error": "not found"}))
    router.get(f"{_FAKE_API_BASE}/v2/document-groups/{_DOC_ID}").mock(return_value=Response(404, json={"error": "not found"}))
    router.get(f"{_FAKE_API_BASE}/documentgroup/template/{_DOC_ID}").mock(return_value=Response(404, json={"error": "not found"}))

    router.get(f"{_FAKE_API_BASE}/document/{_DOC_ID}").mock(return_value=Response(200, json=_document_payload()))
    router.get(f"{_FAKE_API_BASE}/user").mock(return_value=Response(200, json=_user_info_payload()))
    router.post(f"{_FAKE_API_BASE}/document/{_DOC_ID}/invite").mock(return_value=Response(200, json={"status": "sent", "id": "invite_eval_002"}))
    router.post(f"{_FAKE_API_BASE}/document/{_DOC_ID}/download/link").mock(
        return_value=Response(
            200,
            json={"link": f"https://cdn-eval.signnow.com/files/{_DOC_ID}.pdf?token=xyz"},
        )
    )

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


invite_used_expected_doc_id_two_agent = Invariant(
    name="invite_used_expected_doc_id",
    rationale=(
        "The simulator explicitly tells the agent which doc id to use and is "
        "instructed to correct it if the agent substitutes another. If the "
        "invite still goes out against a different id, the agent is ignoring "
        "user corrections — a much worse bug than ignoring a static prompt."
    ),
    check=_send_invite_used_expected_doc,
)


def _user_info_payload() -> dict[str, Any]:
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
    return {
        "id": _DOC_ID,
        "user_id": "user_eval_001",
        "document_name": "Eval document 2",
        "page_count": "1",
        "created": "1700000000",
        "updated": "1700000100",
        "original_filename": "eval2.pdf",
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
                "id": "fi_eval_002",
                "status": "pending",
                "created": "1700000000",
                "email": "client@example.com",
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
