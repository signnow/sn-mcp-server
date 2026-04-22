# MCP eval harness (Python)

Scripted end-to-end regression net for the SignNow MCP tool surface.
Python port of the TypeScript `mcp/eval` harness from the `auto-cources`
repo, adapted to this project's tools and HTTP surface.

## What it does

Runs a full SignNow workflow scenario against the real `sn_mcp_server`
FastMCP server, driven by either a scripted mock agent or a real LLM. All
outbound SignNow HTTP traffic is intercepted by `respx` and replied to
with pydantic-valid fixtures — no network, no real account needed. The run
produces a `RunTrace` (ordered tool calls + driver stats); a set of
**invariants** asserts structural facts about that trace; and the runner
writes a JSON report + Markdown summary.

The invariants are deliberately structural, not snapshot-on-text. Wording
drift between model releases should never fail the harness — a missing
tool call or a bad tool sequence should.

## Running locally

No database, no server to start. The scenario seeds env vars and an in-
process HTTP mock; that's it.

```bash
# MockDriver only — no API keys needed, deterministic, fast.
python -m eval.cli --driver mock

# Real LLM drivers. Set LITELLM_BASE_URL + LITELLM_API_KEY (or the
# provider-specific ANTHROPIC_API_KEY / OPENAI_API_KEY fallbacks).
# Install the SDK first: `pip install anthropic` / `pip install openai`.
python -m eval.cli --driver anthropic
python -m eval.cli --driver openai
python -m eval.cli --driver all --trials 3

# Pick a scenario (default: full-flow). "all" runs every registered scenario.
python -m eval.cli --driver anthropic --scenario two-agent-flow
python -m eval.cli --driver anthropic --scenario all
```

The CLI loads `.env` from the repo root automatically (via
`python-dotenv`), so keys already configured for local development are
picked up without extra shell exports. Use `override=False` semantics —
anything already exported in the shell wins over `.env`.

Reports land in `eval-reports/` by default (override with `--out DIR`).

Pass `--transcripts` to additionally write `<out>/transcripts/<scenario>-
<driver>-trial<N>.md` per run: the full agent ↔ user dialog plus every
tool call's args and result. This is the primary debugging surface for
LLM-simulated scenarios — when `discovery_before_writes` flags, the
transcript tells you *why* the agent skipped discovery.

Model selection for real-LLM drivers is via env:

- `EVAL_ANTHROPIC_MODEL` (default `claude-haiku-4-5`)
- `EVAL_OPENAI_MODEL` (default `gpt-4o-mini`)
- `EVAL_SIMULATOR_MODEL` (default `claude-haiku-4-5`) — model the
  `LLMUserStrategy` uses to role-play the user in two-agent scenarios.

## Reading a report

`report.md` has one row per `(scenario × driver × trial)`:

```
| Scenario  | Driver    | Model            | Turns | Tool calls | Tokens    | $ est   | Result  |
| full-flow | anthropic | claude-haiku-4-5 |     7 |          3 | 3210/1801 | $0.0122 | ✓ pass |
```

Failures include the invariant name + a short detail string — usually
enough to reproduce with the MockDriver.

`report.json` is diffable across runs (keys sorted; `generated_at`
stamped but not part of run data). Use this when A/B-testing a tool-
description change: commit `report.json` before and after, `git diff` it.

## Layout

```
eval/
  cli.py              # argparse entry point (python -m eval.cli)
  runner.py           # orchestrator: seed → server → client → driver → invariants
  types.py            # dataclasses for the trace / invariant / scenario contracts
  invariants.py       # DEFAULT_INVARIANTS and the evaluate() helper
  report.py           # build_report / to_stable_json / to_markdown_summary
  simulators.py       # CannedUserStrategy + LLMUserStrategy
  drivers/
    shared.py         # fetch_tools, call_tool, cost estimator
    mock.py           # deterministic canned sequence
    anthropic.py      # Anthropic Messages API tool-use loop
    openai.py         # OpenAI chat-completions tool loop
  scenarios/
    full_flow.py      # SignNow happy path, scripted user replies
    two_agent_flow.py # same chain, user side driven by LLM simulator
```

## Adding a scenario

1. Create `eval/scenarios/<name>.py` exporting a function that returns a
   `ScenarioDefinition`.
2. `seed()` sets env vars (`SIGNNOW_API_BASE`, credentials) and starts an
   `respx` router with mock responses for the SignNow endpoints the
   scenario exercises. Return a `ScenarioFixture` with a `teardown` that
   stops the router.
3. `read_env()` reads the post-run state invariants care about — e.g.
   `router.calls` for HTTP-level assertions, or any extras stashed in
   `fixture.facts`.
4. Pick a **user strategy** for the `user=` field (see below): canned
   replies for deterministic regression, LLM simulator for goal-driven
   scenarios.
5. Add any scenario-specific invariants in the same file; they're merged
   with `DEFAULT_INVARIANTS` by the runner.
6. Register the builder in `_SCENARIO_BUILDERS` in `eval/cli.py` so
   `--scenario=<name>` and `--scenario=all` can pick it up.

Don't leak state across runs: each `seed()` must produce a fresh router
and the teardown must stop it, or the next run will see stale routes.

## User strategies: canned vs LLM simulator

Scenarios specify how the "user" side of the conversation behaves when the
agent stops without a tool call. Two strategies ship in
`eval/simulators.py`:

- **`CannedUserStrategy(replies=[...])`** — returns a fixed list in order,
  then `None` (which tells the driver to stop). Deterministic, free,
  and what `full_flow.py` uses. Right default when the conversation
  pattern is stable and you want cheap regression runs.
- **`LLMUserStrategy(goal_steps=[...], constraints=[...])`** — routes
  each reply through a second Anthropic model that role-plays a user
  with scripted goals. The simulator sees the running dialog (with roles
  flipped so the agent-under-test is "the human" from its POV) and
  replies "DONE" when every goal is satisfied. Used by
  `two_agent_flow.py`. Right choice when the agent may ask clarifying
  questions a canned reply can't coherently answer, or when you want to
  test that the agent honours corrections the user issues mid-flow.

The simulator has a hard `max_turns` cap (default 20) and obeys a soft
USD budget via the driver's `--budget-usd`. Runs cost ~2× a canned
scenario because every agent turn triggers a simulator turn.

## Adding a driver

A driver implements the `EvalDriver` protocol from `types.py`:

```python
class MyDriver:
    name = "my"
    model = "my-model"

    async def run(self, ctx: DriverContext) -> DriverRunResult:
        # Call ctx.client.call_tool(name, args) in whatever loop your SDK
        # supports. The runner has already wrapped the client with a trace
        # collector, so you don't need to track tool calls yourself — just
        # drive the loop and return message summaries + stats.
        ...
```

Two reference implementations ship:

- **`drivers/anthropic.py`** uses the raw `anthropic` Messages API. The
  TS harness called this the "AgentSdkDriver"; we use the raw SDK because
  the Claude Agent SDK spawns the Claude Code CLI and isn't designed for
  headless CI.
- **`drivers/openai.py`** uses `openai` chat completions with function
  tools. MCP tool schemas are converted to OpenAI's tool format.

Both drivers accept `LITELLM_BASE_URL` + `LITELLM_API_KEY` so all traffic
is cost-tracked through a local LiteLLM proxy when one is configured.

## Why not transcript snapshots?

Two reasons.

First, every LLM release rewrites tool-using prompts, and the *right*
answer reshuffles across runs even at temperature 0. If the harness fails
on that, the fix is to update the snapshot — which defeats the point of
a regression test.

Second, the product bet is that the tool surface itself (names,
descriptions, annotations, parameters) should be robust across models. If
a tool description was rephrased in a way that worked on Claude but
broke on GPT-4o, a snapshot diff on the transcript text would light up
green (because the tested model was fine) while the actual regression
shipped. Structural invariants run across all drivers and catch that.

## Budget guardrails

- `max_turns` default: 30 (override with `--max-turns`).
- `max_tokens_per_response` default: 2000 (tuned in the runner).
- Soft budget cap: `$1.00` per run (override with `--budget-usd`).
  Exceeding aborts the driver with a `RuntimeError`.

Tuned for Haiku 4.5 (~$0.05–0.15/run). Swapping in more expensive models
should come with a compensating `--trials` reduction.

## CI

This harness is a local-CI / developer tool; it does not run on every PR
by default. The MockDriver run is deterministic and cheap enough to land
in CI on demand (e.g. a `run-eval` label gating a GitHub Actions job);
live-LLM runs should stay label-gated to avoid burning the budget on
every push.
