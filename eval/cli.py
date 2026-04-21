"""CLI entry point for the MCP eval harness.

Accepts ``--driver`` (one of ``mock``, ``anthropic``, ``openai``, ``all``),
``--trials`` (default 1), and ``--out`` (default ``./eval-reports``). Exits
non-zero when any invariant fails — CI gates on the same bit.

Run it with ``python -m eval.cli`` from the repo root. No external
dependencies beyond what's already pinned for the server itself; real-LLM
drivers additionally require ``anthropic`` or ``openai`` packages and the
corresponding API keys.

Mirrors ``mcp/eval/cli.ts`` from the TypeScript auto-cources harness.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Load .env before any driver reads os.environ. pydantic-settings reads
# .env only into the Settings model (server config), not into process env,
# so LITELLM_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY wouldn't reach
# the drivers otherwise. python-dotenv is a transitive dep of
# pydantic-settings, so it's always available.
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env", override=False)

from .drivers.anthropic import AnthropicDriver  # noqa: E402
from .drivers.mock import MockDriver  # noqa: E402
from .drivers.openai import OpenAiDriver  # noqa: E402
from .report import build_report, to_markdown_summary, to_stable_json  # noqa: E402
from .runner import RunOneOptions, RunOneResult, run_one  # noqa: E402
from .scenarios.full_flow import build_full_flow_scenario  # noqa: E402
from .scenarios.two_agent_flow import build_two_agent_flow_scenario  # noqa: E402
from .types import EvalDriver, ScenarioDefinition  # noqa: E402

_DriverSelection = str  # "mock" | "anthropic" | "openai" | "all"

# Ordered so --scenario=all runs the cheap canned scenario first and the
# LLM-simulated one after. New scenarios plug in here.
_SCENARIO_BUILDERS: dict[str, Any] = {
    "full-flow": build_full_flow_scenario,
    "two-agent-flow": build_two_agent_flow_scenario,
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m eval.cli",
        description="Run the SignNow MCP eval harness.",
    )
    parser.add_argument(
        "--driver",
        choices=["mock", "anthropic", "openai", "all"],
        default="mock",
        help="Which driver(s) to run (default: mock).",
    )
    parser.add_argument(
        "--scenario",
        choices=[*_SCENARIO_BUILDERS.keys(), "all"],
        default="full-flow",
        help="Which scenario(s) to run (default: full-flow).",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="How many trials per (scenario, driver) pair (default: 1).",
    )
    parser.add_argument(
        "--out",
        default="eval-reports",
        help="Output directory for report.json and report.md (default: eval-reports).",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=30,
        help="Max LLM turns before the runner aborts (default: 30).",
    )
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=1.0,
        help="Soft cost cap per run in USD (default: 1.0).",
    )
    parser.add_argument(
        "--transcripts",
        action="store_true",
        help=("Write full per-run transcripts to <out>/transcripts/<scenario>-<driver>-trial<N>.md — agent ↔ user dialog plus tool calls."),
    )
    return parser.parse_args(argv)


def _drivers_for(selection: _DriverSelection) -> list[EvalDriver]:
    if selection == "mock":
        return [MockDriver()]
    if selection == "anthropic":
        return [AnthropicDriver()]
    if selection == "openai":
        return [OpenAiDriver()]
    return [MockDriver(), AnthropicDriver(), OpenAiDriver()]


def _scenarios_for(selection: str) -> list[ScenarioDefinition]:
    if selection == "all":
        return [build() for build in _SCENARIO_BUILDERS.values()]
    return [_SCENARIO_BUILDERS[selection]()]


def _write_transcript(out_dir: Path, result: RunOneResult, trial: int) -> None:
    """Render the agent ↔ user dialog + tool calls as a single markdown file.

    Dialog is listed first in order, then tool calls in registration order.
    We deliberately don't interleave: drivers don't record which dialog turn
    a given tool call belongs to, and approximating by timestamp would be
    more misleading than helpful when debugging.
    """
    trace = result.trace
    lines: list[str] = []
    lines.append(f"# Transcript: {trace.scenario_name} × {trace.driver_name} × {trace.model} (trial {trial})")
    lines.append("")
    lines.append(f"- started_at: {trace.started_at}")
    lines.append(f"- duration_ms: {trace.duration_ms}")
    lines.append(f"- turns: {trace.stats.turns} (stopped_by_turn_limit={trace.stats.stopped_by_turn_limit})")
    lines.append(f"- tokens in/out: {trace.stats.input_tokens}/{trace.stats.output_tokens} (~${trace.stats.estimated_cost_usd:.4f})")
    if trace.driver_error is not None:
        lines.append(f"- driver_error: {trace.driver_error}")
    lines.append("")

    lines.append("## Invariants")
    for inv in result.invariants:
        mark = "✓" if inv.ok else "✗"
        detail = f" — {inv.detail}" if inv.detail else ""
        lines.append(f"- {mark} {inv.name}{detail}")
    lines.append("")

    lines.append("## Dialog")
    if not trace.dialog:
        lines.append("_(driver does not record a text dialog — e.g. MockDriver)_")
    else:
        for i, turn in enumerate(trace.dialog, start=1):
            role = turn.get("role", "?")
            content = (turn.get("content") or "").strip()
            lines.append(f"### [{i}] {role}")
            lines.append("")
            lines.append(content if content else "_(empty)_")
            lines.append("")

    lines.append("## Tool calls")
    if not trace.tool_calls:
        lines.append("_(none)_")
    else:
        for i, call in enumerate(trace.tool_calls, start=1):
            args_str = _short_json(call.args)
            result_str = _short_json(call.result) if call.error is None else f"ERROR: {call.error.get('message')}"
            lines.append(f"### [{i}] {call.tool} ({call.duration_ms} ms)")
            lines.append("")
            lines.append("**args:**")
            lines.append("")
            lines.append("```json")
            lines.append(args_str)
            lines.append("```")
            lines.append("")
            lines.append("**result:**")
            lines.append("")
            lines.append("```")
            lines.append(result_str)
            lines.append("```")
            lines.append("")

    path = out_dir / f"{trace.scenario_name}-{trace.driver_name}-trial{trial}.md"
    path.write_text("\n".join(lines))


def _short_json(value: Any) -> str:
    """Pretty-print small values; truncate large ones so transcripts stay scrollable."""
    try:
        text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > 4000:
        return text[:4000] + f"\n... [truncated, {len(text) - 4000} chars omitted]"
    return text


async def _main(argv: list[str]) -> int:
    args = _parse_args(argv)
    trials = max(1, args.trials)
    scenarios = _scenarios_for(args.scenario)
    drivers = _drivers_for(args.driver)

    runs: list[tuple[RunOneResult, int]] = []
    for scenario in scenarios:
        for driver in drivers:
            for t in range(trials):
                print(
                    f"[eval] {scenario.name} x {driver.name} x {getattr(driver, 'model', driver.name)} (trial {t + 1}/{trials})",
                    flush=True,
                )
                result = await run_one(
                    RunOneOptions(
                        scenario=scenario,
                        driver=driver,
                        max_turns=args.max_turns,
                        budget_usd=args.budget_usd,
                    )
                )
                runs.append((result, t + 1))
                failed = [r for r in result.invariants if not r.ok]
                if result.trace.driver_error is not None:
                    print(f"  FAIL driver_error: {result.trace.driver_error}", flush=True)
                elif failed:
                    names = ", ".join(f.name for f in failed)
                    print(f"  FAIL ({names})", flush=True)
                else:
                    print("  PASS", flush=True)

    report = build_report([(r.trace, r.invariants) for r, _ in runs])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(to_stable_json(report))
    (out_dir / "report.md").write_text(to_markdown_summary(report))

    if args.transcripts:
        transcripts_dir = out_dir / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        for result, trial_n in runs:
            _write_transcript(transcripts_dir, result, trial_n)
        print(f"[eval] transcripts -> {transcripts_dir}/", flush=True)

    summary = report.summary
    print(
        f"\n[eval] {summary['passed']}/{summary['total']} passed. Report -> {out_dir}/report.md",
        flush=True,
    )
    return 0 if summary["failed"] == 0 else 1


def main() -> None:
    try:
        code = asyncio.run(_main(sys.argv[1:]))
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
