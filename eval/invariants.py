"""Default invariant set.

Design rule: invariants assert **structural facts**, not transcript text.
The agent is free to phrase its messages however it wants; what we pin is
"did the tool sequence make sense", "did the mock API see the right
requests", "did any tool call error out". Snapshot-on-text is deliberately
avoided — wording drift on every model release should not fail this harness.

Mirrors ``mcp/eval/invariants.ts`` from the TypeScript auto-cources harness,
adapted to the SignNow tool surface (send_invite / get_invite_status /
get_document_download_link / list_all_templates / ...).
"""

from __future__ import annotations

from .types import Invariant, InvariantEnv, InvariantResult, RunTrace

# Tools that modify SignNow state — must be preceded by a discovery tool so
# the agent knows what entity it's acting on. The TS harness phrased this as
# "no writes before start_session"; the SignNow equivalent is "no writes
# until we've listed templates or documents at least once".
_DISCOVERY_TOOLS = {
    "list_all_templates",
    "list_documents",
    "list_contacts",
    "signnow_skills",
}

_WRITE_TOOLS = {
    "send_invite",
    "send_invite_reminder",
    "create_embedded_invite",
    "create_embedded_sending",
    "create_embedded_editor",
    "create_template",
    "create_from_template",
    "update_document_fields",
    "upload_document",
}


def _discovery_before_writes(trace: RunTrace, _env: InvariantEnv) -> str | None:
    """Any write tool must be preceded by at least one discovery call."""
    discovered = False
    for i, c in enumerate(trace.tool_calls):
        if c.tool in _DISCOVERY_TOOLS:
            discovered = True
        if c.tool in _WRITE_TOOLS and not discovered:
            return f"write tool {c.tool} called at position {i} before any discovery tool"
    return None


discovery_before_writes = Invariant(
    name="discovery_before_writes",
    rationale=(
        "Write tools modify SignNow state; firing them before a discovery call "
        "means the agent guessed an entity_id instead of resolving one. This is "
        "the SignNow equivalent of 'never submit before start_session'."
    ),
    check=_discovery_before_writes,
)


def _zero_tool_errors(trace: RunTrace, _env: InvariantEnv) -> str | None:
    failed = [c for c in trace.tool_calls if c.error is not None]
    if not failed:
        return None
    detail = "; ".join(f"{c.tool}({(c.error or {}).get('message', '')})" for c in failed[:3])
    return f"{len(failed)} tool call(s) errored: {detail}"


zero_tool_errors = Invariant(
    name="zero_tool_errors",
    rationale=("A correctly-prompted agent should never trigger tool-argument validation failures — those signal drift between tool descriptions and model behaviour."),
    check=_zero_tool_errors,
)


def _status_after_invite(trace: RunTrace, _env: InvariantEnv) -> str | None:
    """If we sent an invite, we must also check its status."""
    invite_positions = [i for i, c in enumerate(trace.tool_calls) if c.tool in {"send_invite", "create_embedded_invite"}]
    if not invite_positions:
        return None
    status_positions = [i for i, c in enumerate(trace.tool_calls) if c.tool == "get_invite_status"]
    if not status_positions:
        return "send_invite was called but get_invite_status never was"
    first_invite = invite_positions[0]
    last_status = status_positions[-1]
    if last_status <= first_invite:
        return "get_invite_status was called but only before send_invite"
    return None


status_after_invite = Invariant(
    name="status_after_invite",
    rationale=("After sending an invite, the happy path checks delivery/acceptance status. Skipping that leaves the user without any confirmation and hides bugs in the status tool."),
    check=_status_after_invite,
)


def _did_not_lecture(trace: RunTrace, _env: InvariantEnv) -> str | None:
    tool_calls = len(trace.tool_calls)
    if tool_calls == 0:
        return "no tool calls recorded (cannot compute ratio)"
    ratio = trace.stats.output_tokens / tool_calls
    threshold = 1500.0
    if ratio > threshold:
        return f"output tokens per tool call = {ratio:.1f} (threshold {threshold:.0f})"
    return None


did_not_lecture = Invariant(
    name="did_not_lecture",
    rationale=("An agent that lectures instead of acting produces a lot of output tokens per tool call. Coarse sanity check, not a precise measure."),
    check=_did_not_lecture,
)


def _stayed_within_turn_budget(trace: RunTrace, _env: InvariantEnv) -> str | None:
    if trace.stats.stopped_by_turn_limit:
        return f"driver stopped after {trace.stats.turns} turns (max)"
    return None


stayed_within_turn_budget = Invariant(
    name="stayed_within_turn_budget",
    rationale=("Hitting max_turns means the runner aborted mid-flow, not that the agent finished. We want a clean stop."),
    check=_stayed_within_turn_budget,
)


DEFAULT_INVARIANTS: list[Invariant] = [
    discovery_before_writes,
    zero_tool_errors,
    status_after_invite,
    did_not_lecture,
    stayed_within_turn_budget,
]


def evaluate(
    invariants: list[Invariant],
    trace: RunTrace,
    env: InvariantEnv,
) -> list[InvariantResult]:
    """Evaluate a set of invariants against one run trace + environment."""
    results: list[InvariantResult] = []
    for inv in invariants:
        detail = inv.check(trace, env)
        results.append(InvariantResult(name=inv.name, ok=detail is None, detail=detail))
    return results
