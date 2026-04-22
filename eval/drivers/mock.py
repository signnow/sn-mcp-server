"""Deterministic driver that executes a canned sequence of tool calls.

Used exclusively for testing the harness itself — it proves that the
runner, the trace collector, the invariant engine, and the report all
work without any LLM in the loop.

The canned script is deliberately minimal: exactly enough to satisfy
``discovery_before_writes`` (via a pure-filesystem ``signnow_skills``
call), then the core happy path on the doc_id the scenario pre-seeds
into the prompt. No fake listing of templates/documents — that would
require mocking a broad HTTP surface this scenario doesn't need.

Mirrors ``mcp/eval/drivers/mock.ts`` from the TypeScript auto-cources
harness, adapted to the SignNow tool surface.
"""

from __future__ import annotations

import re

from ..types import DriverContext, DriverRunResult, DriverStats
from .shared import call_tool, fetch_tools


class MockDriver:
    name = "mock"
    model = "mock-scripted"

    async def run(self, ctx: DriverContext) -> DriverRunResult:
        messages: list[dict[str, str]] = [{"role": "user", "summary": ctx.scenario_prompt[:80]}]

        await fetch_tools(ctx.client)

        # Discovery: pure filesystem read, no HTTP needed, satisfies
        # discovery_before_writes before we start touching SignNow state.
        await call_tool(ctx.client, "signnow_skills", {})
        messages.append({"role": "tool", "summary": "signnow_skills"})

        doc_id = _extract_doc_id(ctx.scenario_prompt)
        if not doc_id:
            return _finish(messages, stopped=False, turns=1)

        await call_tool(
            ctx.client,
            "send_invite",
            {
                "entity_id": doc_id,
                "entity_type": "document",
                "orders": [
                    {
                        "order": 1,
                        "recipients": [
                            {
                                "email": "recipient@example.com",
                                "role": "Signer 1",
                                "action": "sign",
                            }
                        ],
                    }
                ],
            },
        )
        messages.append({"role": "tool", "summary": "send_invite"})

        await call_tool(
            ctx.client,
            "get_invite_status",
            {"entity_id": doc_id, "entity_type": "document"},
        )
        messages.append({"role": "tool", "summary": "get_invite_status"})

        await call_tool(
            ctx.client,
            "get_document_download_link",
            {"entity_id": doc_id, "entity_type": "document"},
        )
        messages.append({"role": "tool", "summary": "get_document_download_link"})

        return _finish(messages, stopped=False, turns=4)


def _finish(messages: list[dict[str, str]], stopped: bool, turns: int) -> DriverRunResult:
    return DriverRunResult(
        messages=messages,
        stats=DriverStats(
            turns=turns,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            model="mock-scripted",
            stopped_by_turn_limit=stopped,
        ),
    )


_DOC_ID_RE = re.compile(r"'(doc_[A-Za-z0-9_]+)'")


def _extract_doc_id(prompt: str) -> str | None:
    """Fish the document id out of the scenario prompt.

    The full_flow scenario quotes the id inline: ``...send document 'doc_eval_001'...``.
    We pick up the first match; future scenarios that need different shapes
    should provide their own mock driver rather than complicate this one.
    """
    m = _DOC_ID_RE.search(prompt)
    return m.group(1) if m else None
