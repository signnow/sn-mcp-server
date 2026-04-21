"""Orchestrator: one scenario × one driver → one trace + invariant results.

Steps, in order:

1. ``scenario.seed()`` — set env vars, start respx, register routes.
2. ``create_server()`` — build the FastMCP server. Env must be set first.
3. ``fastmcp.Client(server)`` — connect in memory; no sockets.
4. Wrap ``client.call_tool`` with a tracer so every call is recorded on a
   shared :class:`ToolCallRecord` list.
5. Run the driver inside the client's ``async with`` context.
6. ``scenario.read_env()`` + ``scenario.teardown()`` — read mock state and
   tear the fixture down (respx stop, env restore).
7. ``evaluate(DEFAULT_INVARIANTS + scenario.invariants, trace, env)`` — run
   checks.

Every call is hermetic: fresh server, fresh client, fresh trace. Parallel
runs are not supported by the default scenario seed (it mutates process
env), so the CLI runs sequentially.

Mirrors ``mcp/eval/runner.ts`` from the TypeScript auto-cources harness.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastmcp import Client

from sn_mcp_server.server import create_server

from .invariants import DEFAULT_INVARIANTS, evaluate
from .types import (
    DriverContext,
    DriverRunResult,
    DriverStats,
    EvalDriver,
    InvariantResult,
    RunTrace,
    ScenarioDefinition,
    ToolCallRecord,
)


@dataclass
class RunOneOptions:
    scenario: ScenarioDefinition
    driver: EvalDriver
    max_turns: int = 30
    max_tokens_per_response: int = 2000
    budget_usd: float = 1.0


@dataclass
class RunOneResult:
    trace: RunTrace
    invariants: list[InvariantResult]


async def run_one(opts: RunOneOptions) -> RunOneResult:
    scenario = opts.scenario
    driver = opts.driver

    fixture = await scenario.seed()
    tool_calls: list[ToolCallRecord] = []
    run_started_at_mono = time.monotonic()
    run_started_at_wall = datetime.now(timezone.utc)

    server = create_server()

    driver_result: DriverRunResult | None = None
    driver_error: str | None = None

    async with Client(server) as client:
        _wrap_client_with_trace(client, tool_calls, run_started_at_mono)
        try:
            driver_result = await driver.run(
                DriverContext(
                    client=client,
                    server=server,
                    scenario_prompt=scenario.initial_prompt,
                    max_turns=opts.max_turns,
                    max_tokens_per_response=opts.max_tokens_per_response,
                    budget_usd=opts.budget_usd,
                    user=scenario.user,
                )
            )
        except Exception as err:  # noqa: BLE001
            driver_error = f"{type(err).__name__}: {err}"

    duration_ms = int((time.monotonic() - run_started_at_mono) * 1000)

    try:
        env = await scenario.read_env(fixture)
    finally:
        if fixture.teardown is not None:
            await fixture.teardown()

    stats = (
        driver_result.stats
        if driver_result is not None
        else DriverStats(
            turns=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            model=getattr(driver, "model", driver.name),
            stopped_by_turn_limit=False,
        )
    )

    trace = RunTrace(
        scenario_name=scenario.name,
        driver_name=driver.name,
        model=stats.model,
        started_at=run_started_at_wall.isoformat(),
        duration_ms=duration_ms,
        tool_calls=tool_calls,
        messages=driver_result.messages if driver_result is not None else [],
        stats=stats,
        driver_error=driver_error,
        dialog=driver_result.dialog if driver_result is not None else [],
    )

    results = evaluate(
        [*DEFAULT_INVARIANTS, *scenario.invariants],
        trace,
        env,
    )
    return RunOneResult(trace=trace, invariants=results)


def _wrap_client_with_trace(
    client: Client[Any],
    trace: list[ToolCallRecord],
    run_started_at_mono: float,
) -> None:
    """Monkey-patch ``client.call_tool`` to append a :class:`ToolCallRecord` per call.

    fastmcp's Client has no "backend" seam like the TS SDK; wrapping the
    public ``call_tool`` method is the cleanest spot. Every driver goes
    through this method, so recording here catches every tool invocation
    regardless of driver shape.
    """
    original = client.call_tool

    async def traced_call_tool(
        name: str,
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        at_ms = int((time.monotonic() - run_started_at_mono) * 1000)
        t0 = time.monotonic()
        record = ToolCallRecord(
            tool=name,
            args=arguments or {},
            at_ms=at_ms,
            duration_ms=0,
        )
        try:
            result = await original(name, arguments, **kwargs)
        except Exception as err:  # noqa: BLE001
            record.duration_ms = int((time.monotonic() - t0) * 1000)
            record.error = {"message": f"{type(err).__name__}: {err}"}
            trace.append(record)
            raise
        record.duration_ms = int((time.monotonic() - t0) * 1000)
        if getattr(result, "is_error", False):
            record.error = {"message": _extract_error_message(result)}
        else:
            record.result = _summarize_result(result)
        trace.append(record)
        return result

    client.call_tool = traced_call_tool  # type: ignore[method-assign]


def _extract_error_message(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for c in content:
            text = getattr(c, "text", None)
            if isinstance(text, str) and text:
                return text
    return "tool returned is_error=True"


def _summarize_result(result: Any) -> Any:
    """Keep traces light: prefer structured_content, else data, else drop content blobs."""
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    data = getattr(result, "data", None)
    if data is not None:
        return data
    content = getattr(result, "content", None)
    if isinstance(content, list):
        parts: list[str] = []
        for c in content:
            text = getattr(c, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
    return None
