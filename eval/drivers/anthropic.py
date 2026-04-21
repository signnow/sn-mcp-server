"""Tool-loop driver backed by the Anthropic Messages API.

The TS harness labels this the "AgentSdkDriver" — historically we planned
to use the Claude Agent SDK, but that SDK spawns the Claude Code CLI under
the hood and isn't suitable for headless CI. The raw Messages API gives us
full control over the tool-calling loop and is a closer match for how
other providers behave (→ fair cross-driver comparison).

The driver is point-and-shoot: hand it a scenario prompt and a set of MCP
tools, and it runs a classic "call tools until the model says stop" loop.
Every tool call goes through the fastmcp :class:`Client`, which in turn
hits the trace-wrapped server the runner installed — that's how tool calls
land in the trace.

Routing through LiteLLM: set ``LITELLM_BASE_URL`` to the local proxy and
``LITELLM_API_KEY`` to the proxy's key. The driver forwards both via
``base_url`` / ``api_key``. If only ``ANTHROPIC_API_KEY`` is set, we talk
to Anthropic directly.

Mirrors ``mcp/eval/drivers/anthropic.ts`` from the TypeScript auto-cources
harness.
"""

from __future__ import annotations

import os
from typing import Any

from ..types import DriverContext, DriverRunResult, DriverStats
from .shared import call_tool, estimate_cost_usd, fetch_tools


class AnthropicDriver:
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("EVAL_ANTHROPIC_MODEL", "claude-haiku-4-5")

    async def run(self, ctx: DriverContext) -> DriverRunResult:
        try:
            from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient
        except ImportError as err:  # pragma: no cover
            raise RuntimeError("AnthropicDriver requires the 'anthropic' package. Install with: pip install anthropic") from err

        base_url = os.environ.get("LITELLM_BASE_URL")
        api_key = os.environ.get("LITELLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("AnthropicDriver requires LITELLM_API_KEY or ANTHROPIC_API_KEY in env")
        # Build an explicit AsyncClient so respx's pass-through machinery sees
        # it. The SDK's default client uses a transport chain that bypasses
        # respx on pass-through routes, causing empty-body / APIConnectionError
        # when a scenario seed has respx.start() active.
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "http_client": DefaultAsyncHttpxClient(),
        }
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncAnthropic(**kwargs)

        tools = await fetch_tools(ctx.client)
        anthropic_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]

        messages: list[dict[str, Any]] = [{"role": "user", "content": ctx.scenario_prompt}]
        summary: list[dict[str, str]] = [{"role": "user", "summary": ctx.scenario_prompt[:80]}]
        input_tokens = 0
        output_tokens = 0
        learner_idx = 0
        stopped_by_turn_limit = True

        for _turn in range(ctx.max_turns):
            response = await client.messages.create(
                model=self.model,
                max_tokens=ctx.max_tokens_per_response,
                tools=anthropic_tools,
                messages=messages,
            )
            input_tokens += getattr(response.usage, "input_tokens", 0) or 0
            output_tokens += getattr(response.usage, "output_tokens", 0) or 0
            cost = estimate_cost_usd(input_tokens, output_tokens)
            if cost > ctx.budget_usd:
                raise RuntimeError(f"budget exceeded: est ${cost:.4f} > cap ${ctx.budget_usd}")

            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
            text = "\n".join(getattr(b, "text", "") for b in text_blocks)
            if text:
                summary.append({"role": "assistant", "summary": text[:80]})
            messages.append({"role": "assistant", "content": [_block_to_dict(b) for b in response.content]})

            if not tool_uses:
                if learner_idx < len(ctx.simulated_learner_replies):
                    reply = ctx.simulated_learner_replies[learner_idx]
                    learner_idx += 1
                    messages.append({"role": "user", "content": reply})
                    summary.append({"role": "user", "summary": reply[:80]})
                    continue
                stopped_by_turn_limit = False
                break

            tool_results: list[dict[str, Any]] = []
            for use in tool_uses:
                args = use.input or {}
                if not isinstance(args, dict):
                    args = {}
                result_text = await call_tool(ctx.client, use.name, args)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": use.id,
                    "content": result_text,
                    "is_error": result_text.startswith("TOOL_ERROR:"),
                })
                summary.append({"role": "tool", "summary": use.name})
            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason == "end_turn":
                stopped_by_turn_limit = False
                break

        return DriverRunResult(
            messages=summary,
            stats=DriverStats(
                turns=min(
                    ctx.max_turns,
                    sum(1 for m in summary if m["role"] == "assistant"),
                ),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimate_cost_usd(input_tokens, output_tokens),
                model=self.model,
                stopped_by_turn_limit=stopped_by_turn_limit,
            ),
        )


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Convert an Anthropic content block back to a dict for the next turn."""
    btype = getattr(block, "type", None)
    if btype == "text":
        return {"type": "text", "text": getattr(block, "text", "")}
    if btype == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return {"type": str(btype)}
