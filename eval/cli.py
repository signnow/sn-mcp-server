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
import sys
from pathlib import Path

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
from .types import EvalDriver  # noqa: E402

_DriverSelection = str  # "mock" | "anthropic" | "openai" | "all"


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
    return parser.parse_args(argv)


def _drivers_for(selection: _DriverSelection) -> list[EvalDriver]:
    if selection == "mock":
        return [MockDriver()]
    if selection == "anthropic":
        return [AnthropicDriver()]
    if selection == "openai":
        return [OpenAiDriver()]
    return [MockDriver(), AnthropicDriver(), OpenAiDriver()]


async def _main(argv: list[str]) -> int:
    args = _parse_args(argv)
    trials = max(1, args.trials)
    scenario = build_full_flow_scenario()
    drivers = _drivers_for(args.driver)

    runs: list[RunOneResult] = []
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
            runs.append(result)
            failed = [r for r in result.invariants if not r.ok]
            if result.trace.driver_error is not None:
                print(f"  FAIL driver_error: {result.trace.driver_error}", flush=True)
            elif failed:
                names = ", ".join(f.name for f in failed)
                print(f"  FAIL ({names})", flush=True)
            else:
                print("  PASS", flush=True)

    report = build_report([(r.trace, r.invariants) for r in runs])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(to_stable_json(report))
    (out_dir / "report.md").write_text(to_markdown_summary(report))

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
