"""Report builder: stable JSON + Markdown summary.

Keys are sorted at every level so diffs across runs are minimal — legible
even when the LLM's wording shifts between runs. Mirrors
``mcp/eval/report.ts`` from the TypeScript auto-cources harness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .types import InvariantResult, RunTrace


@dataclass
class EvalRunReport:
    scenario: str
    driver: str
    model: str
    duration_ms: int
    tokens_in: int
    tokens_out: int
    estimated_cost_usd: float
    turns: int
    tool_call_count: int
    tool_sequence: list[str]
    invariants: list[InvariantResult]
    passed: bool
    driver_error: str | None


@dataclass
class EvalReport:
    schema: str
    generated_at: str
    runs: list[EvalRunReport]
    summary: dict[str, Any] = field(default_factory=dict)


def build_report(runs: list[tuple[RunTrace, list[InvariantResult]]]) -> EvalReport:
    run_reports: list[EvalRunReport] = []
    for trace, invariants in runs:
        passed = all(r.ok for r in invariants) and trace.driver_error is None
        run_reports.append(
            EvalRunReport(
                scenario=trace.scenario_name,
                driver=trace.driver_name,
                model=trace.model,
                duration_ms=round(trace.duration_ms),
                tokens_in=trace.stats.input_tokens,
                tokens_out=trace.stats.output_tokens,
                estimated_cost_usd=_round(trace.stats.estimated_cost_usd, 4),
                turns=trace.stats.turns,
                tool_call_count=len(trace.tool_calls),
                tool_sequence=[c.tool for c in trace.tool_calls],
                invariants=invariants,
                passed=passed,
                driver_error=trace.driver_error,
            )
        )
    invariants_failed: dict[str, int] = {}
    for r in run_reports:
        for inv in r.invariants:
            if not inv.ok:
                invariants_failed[inv.name] = invariants_failed.get(inv.name, 0) + 1
    return EvalReport(
        schema="mcp-eval.v1",
        # placeholder; replaced at serialization time
        generated_at=datetime.fromtimestamp(0, tz=timezone.utc).isoformat(),
        runs=run_reports,
        summary={
            "total": len(run_reports),
            "passed": sum(1 for r in run_reports if r.passed),
            "failed": sum(1 for r in run_reports if not r.passed),
            "invariants_failed": invariants_failed,
        },
    )


def to_stable_json(report: EvalReport) -> str:
    """Serialize with sorted keys at every level so diffs across runs are minimal."""
    stamped = _report_to_dict(report)
    stamped["generated_at"] = datetime.now(timezone.utc).isoformat()
    return json.dumps(stamped, sort_keys=True, indent=2) + "\n"


def to_markdown_summary(report: EvalReport) -> str:
    lines: list[str] = []
    lines.append("# MCP eval report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    s = report.summary
    lines.append(f"**Runs:** {s['total']} · **Passed:** {s['passed']} · **Failed:** {s['failed']}")
    lines.append("")
    lines.append("| Scenario | Driver | Model | Turns | Tool calls | Tokens (in/out) | $ est | Result |")
    lines.append("|---|---|---|---:|---:|---:|---:|---|")
    for r in report.runs:
        result = "✓ pass" if r.passed else "✗ fail"
        lines.append(f"| {r.scenario} | {r.driver} | {r.model} | {r.turns} | {r.tool_call_count} | {r.tokens_in}/{r.tokens_out} | ${r.estimated_cost_usd:.4f} | {result} |")
    lines.append("")
    failed_runs = [r for r in report.runs if not r.passed]
    if failed_runs:
        lines.append("## Failures")
        lines.append("")
        for r in failed_runs:
            lines.append(f"### {r.scenario} · {r.driver} · {r.model}")
            lines.append("")
            if r.driver_error:
                lines.append(f"- Driver error: `{r.driver_error}`")
            for inv in r.invariants:
                if not inv.ok:
                    lines.append(f"- **{inv.name}** — {inv.detail}")
            lines.append("")
    return "\n".join(lines)


def _report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "schema": report.schema,
        "generated_at": report.generated_at,
        "runs": [
            {
                "scenario": r.scenario,
                "driver": r.driver,
                "model": r.model,
                "duration_ms": r.duration_ms,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "estimated_cost_usd": r.estimated_cost_usd,
                "turns": r.turns,
                "tool_call_count": r.tool_call_count,
                "tool_sequence": list(r.tool_sequence),
                "invariants": [{"name": inv.name, "ok": inv.ok, "detail": inv.detail} for inv in r.invariants],
                "passed": r.passed,
                "driver_error": r.driver_error,
            }
            for r in report.runs
        ],
        "summary": report.summary,
    }


def _round(n: float, decimals: int) -> float:
    factor = 10**decimals
    return round(n * factor) / factor
