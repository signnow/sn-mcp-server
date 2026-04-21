"""Types for the MCP eval harness.

Every scenario x driver run produces a :class:`RunTrace`; invariants assert
structural facts on the trace rather than pinning specific LLM wording.

Mirrors ``mcp/eval/types.ts`` from the TypeScript auto-cources harness.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from fastmcp import Client, FastMCP


@dataclass
class ToolCallRecord:
    """One tool call observed on the MCP client boundary."""

    tool: str
    """Tool name as it was invoked (e.g. ``send_invite``)."""

    args: Any
    """Raw arguments the driver passed to the tool."""

    at_ms: int
    """Monotonic ms since run start, for debugging — not used in invariants."""

    duration_ms: int
    """Wall-clock duration of the call in ms."""

    result: Any = None
    """Structured result returned by the MCP server (absent on error)."""

    error: dict[str, Any] | None = None
    """Error summary when the call failed (JSON-RPC or tool-level)."""


@dataclass
class DriverStats:
    """Cumulative stats a driver reports at end of run."""

    turns: int
    """Total LLM turns (request -> response round trips)."""

    input_tokens: int
    """Cumulative input tokens across all turns, when the provider reports them."""

    output_tokens: int
    """Cumulative output tokens across all turns, when the provider reports them."""

    estimated_cost_usd: float
    """Coarse cost estimate in USD (optional; drivers may leave it at 0)."""

    model: str
    """Human-readable model identifier as resolved by the provider."""

    stopped_by_turn_limit: bool
    """Whether the run hit the ``max_turns`` guard before the agent finished."""


@dataclass
class RunTrace:
    """Complete record of one scenario x driver run."""

    scenario_name: str
    driver_name: str
    model: str
    started_at: str
    duration_ms: int
    tool_calls: list[ToolCallRecord]
    messages: list[dict[str, str]]
    """Truncated-to-80-char summary used in the report table."""

    stats: DriverStats
    driver_error: str | None = None
    dialog: list[dict[str, str]] = field(default_factory=list)
    """Full text-only agent ↔ user turns — used by --transcripts, not by the report."""


class UserStrategy(Protocol):
    """Produces the next "user" utterance when the agent pauses without tool calls.

    Two reference implementations ship (see ``eval/simulators.py``):

    - :class:`~eval.simulators.CannedUserStrategy` — returns a hand-written list
      of replies in order. Used by the classic regression scenarios.
    - :class:`~eval.simulators.LLMUserStrategy` — routes each reply through a
      second LLM that role-plays a user with a scripted goal. Used by two-agent
      scenarios where canned replies are too brittle (agent may ask a
      clarifying question that a fixed reply won't address).

    ``history`` is the running user↔assistant dialog with tool calls stripped.
    Items are ``{"role": "user"|"assistant", "content": str}``. Return the next
    reply string, or ``None`` to signal "no more replies, let the agent stop".
    """

    async def next_reply(self, history: list[dict[str, str]]) -> str | None: ...


@dataclass
class DriverContext:
    """Inputs the runner hands to a driver's ``run()`` method."""

    client: Client[Any]
    """Connected fastmcp Client bound to the in-memory server."""

    server: FastMCP[Any]
    """The MCP server instance (for drivers that want to introspect it)."""

    scenario_prompt: str
    """Initial prompt handed to the agent."""

    max_turns: int
    """Hard cap on LLM turns before the runner aborts. Default: 30."""

    max_tokens_per_response: int
    """Hard cap on response tokens per LLM call. Default: 2000."""

    budget_usd: float
    """Abort when cumulative cost exceeds this — defence in depth."""

    user: UserStrategy
    """Strategy for producing replies when the agent stops without tool calls."""


@dataclass
class DriverRunResult:
    """Partial trace data a driver returns. Tool calls are collected by the runner."""

    messages: list[dict[str, str]]
    stats: DriverStats
    dialog: list[dict[str, str]] = field(default_factory=list)
    """Full-text agent ↔ user turns for --transcripts. Drivers without an LLM
    loop (e.g. the mock driver) can leave this empty."""


class EvalDriver(Protocol):
    """A driver runs one scenario end to end."""

    name: str
    model: str

    async def run(self, ctx: DriverContext) -> DriverRunResult: ...


@dataclass
class InvariantEnv:
    """Post-run environment snapshot that invariants can check."""

    mock_requests: list[dict[str, Any]] = field(default_factory=list)
    """HTTP requests the mock SignNow server observed, in arrival order."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Scenario-specific extras for scenario-specific invariants."""


@dataclass
class InvariantResult:
    name: str
    ok: bool
    detail: str | None


@dataclass
class Invariant:
    """One structural check against a run trace + environment."""

    name: str
    """Short, stable name — reported verbatim in JSON and Markdown output."""

    rationale: str
    """Human-readable explanation of what the invariant protects against."""

    check: Callable[[RunTrace, InvariantEnv], str | None]
    """Returns ``None`` on pass, or a failure message describing what was observed."""


@dataclass
class ScenarioFixture:
    """Scenario-scoped facts the runner and invariants need."""

    facts: dict[str, Any]
    """Arbitrary per-scenario data the ``read_env`` implementation may need."""

    teardown: Callable[[], Awaitable[None]] | None = None
    """Optional teardown hook the runner calls after the driver finishes."""


@dataclass
class ScenarioDefinition:
    """One end-to-end scenario definition."""

    name: str
    """Stable id used in reports and CLI output."""

    summary: str
    """One-line summary."""

    initial_prompt: str
    """Initial prompt handed to the agent."""

    user: UserStrategy
    """Produces replies between agent turns. Canned list or LLM-driven simulator."""

    invariants: list[Invariant]
    """Invariants this scenario must satisfy. Merged with the default set in the runner."""

    seed: Callable[[], Awaitable[ScenarioFixture]]
    """Sets up fixtures (mock servers, env vars) and returns a :class:`ScenarioFixture`."""

    read_env: Callable[[ScenarioFixture], Awaitable[InvariantEnv]]
    """Reads back post-run environment the invariants need."""
