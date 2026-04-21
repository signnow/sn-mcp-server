"""Tool-loop driver backed by the OpenAI chat-completions API.

Talks to LiteLLM in OpenAI-compat mode (or directly to OpenAI if you
insist). The point of having an OpenAI-shaped driver next to the
Anthropic-shaped one is to prove our MCP tool descriptions survive intact
across provider SDKs — if a tool description reads wrong on GPT-4o but
fine on Haiku, that's a real regression we want to catch.

Env:
    - ``LITELLM_BASE_URL`` + ``LITELLM_API_KEY`` (preferred, cost-tracked)
    - or ``OPENAI_API_KEY`` (direct, no proxy)

Mirrors ``mcp/eval/drivers/openai.ts`` from the TypeScript auto-cources
harness.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..types import DriverContext, DriverRunResult, DriverStats
from .shared import call_tool, estimate_cost_usd, fetch_tools


class OpenAiDriver:
    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("EVAL_OPENAI_MODEL", "gpt-4o-mini")

    async def run(self, ctx: DriverContext) -> DriverRunResult:
        try:
            from openai import AsyncOpenAI, DefaultAsyncHttpxClient
        except ImportError as err:  # pragma: no cover
            raise RuntimeError("OpenAiDriver requires the 'openai' package. Install with: pip install openai") from err

        base_url = os.environ.get("LITELLM_BASE_URL")
        api_key = os.environ.get("LITELLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OpenAiDriver requires LITELLM_API_KEY or OPENAI_API_KEY in env")
        # See AnthropicDriver for why we pass an explicit http_client —
        # respx pass-through breaks with the SDK's default transport chain.
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "http_client": DefaultAsyncHttpxClient(),
        }
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncOpenAI(**kwargs)

        mcp_tools = await fetch_tools(ctx.client)
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in mcp_tools
        ]

        messages: list[dict[str, Any]] = [{"role": "user", "content": ctx.scenario_prompt}]
        summary: list[dict[str, str]] = [{"role": "user", "summary": ctx.scenario_prompt[:80]}]
        # Text-only dialog handed to the user simulator. Tool calls/results are
        # stripped — the simulator doesn't need to see them to role-play a user.
        dialog: list[dict[str, str]] = [{"role": "user", "content": ctx.scenario_prompt}]
        input_tokens = 0
        output_tokens = 0
        stopped_by_turn_limit = True

        for _turn in range(ctx.max_turns):
            response = await client.chat.completions.create(
                model=self.model,
                max_tokens=ctx.max_tokens_per_response,
                tools=openai_tools,
                messages=messages,
            )
            if response.usage:
                input_tokens += response.usage.prompt_tokens or 0
                output_tokens += response.usage.completion_tokens or 0
            cost = estimate_cost_usd(input_tokens, output_tokens)
            if cost > ctx.budget_usd:
                raise RuntimeError(f"budget exceeded: est ${cost:.4f} > cap ${ctx.budget_usd}")

            choice = response.choices[0]
            msg = choice.message

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content,
            }
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)
            if msg.content:
                summary.append({"role": "assistant", "summary": str(msg.content)[:80]})
                dialog.append({"role": "assistant", "content": str(msg.content)})

            tool_calls = msg.tool_calls or []
            if not tool_calls:
                reply = await ctx.user.next_reply(dialog)
                if reply is None:
                    stopped_by_turn_limit = False
                    break
                messages.append({"role": "user", "content": reply})
                summary.append({"role": "user", "summary": reply[:80]})
                dialog.append({"role": "user", "content": reply})
                continue

            for tc in tool_calls:
                if tc.type != "function":
                    continue
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result_text = await call_tool(ctx.client, tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })
                summary.append({"role": "tool", "summary": tc.function.name})

            if choice.finish_reason == "stop":
                stopped_by_turn_limit = False
                break

        return DriverRunResult(
            messages=summary,
            dialog=dialog,
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
