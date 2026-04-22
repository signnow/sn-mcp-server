"""Helpers shared by the mock, Anthropic, and OpenAI drivers.

The fastmcp :class:`Client` already gives us a typed handle to the server —
we just need to list its tools and reshape them into each provider's
preferred tool schema.

Mirrors ``mcp/eval/drivers/shared.ts`` from the TypeScript auto-cources
harness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastmcp import Client


@dataclass
class ProviderTool:
    name: str
    description: str
    input_schema: dict[str, Any]


async def fetch_tools(client: Client[Any]) -> list[ProviderTool]:
    """Fetch the tool list once per run."""
    tools = await client.list_tools()
    out: list[ProviderTool] = []
    for t in tools:
        schema = dict(t.inputSchema) if t.inputSchema else {"type": "object", "properties": {}}
        out.append(
            ProviderTool(
                name=t.name,
                description=t.description or "",
                input_schema=schema,
            )
        )
    return out


async def call_tool(
    client: Client[Any],
    name: str,
    args: dict[str, Any],
) -> str:
    """Dispatch one tool call through the MCP client.

    Returns the stringified payload the LLM should see. On error, returns a
    short ``TOOL_ERROR:`` message instead of raising — the runner's tracer
    already captured the failure, and we want the LLM to recover rather than
    abort the whole run.
    """
    try:
        result = await client.call_tool(name, args, raise_on_error=False)
        if result.is_error:
            text = _extract_text(result.content)
            return f"TOOL_ERROR: {text or 'unknown'}"
        if result.structured_content is not None:
            return json.dumps(result.structured_content, default=str)
        if result.data is not None:
            try:
                return json.dumps(result.data, default=str)
            except TypeError:
                return str(result.data)
        return _extract_text(result.content) or "{}"
    except Exception as err:  # noqa: BLE001
        return f"TOOL_ERROR: {err}"


def _extract_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for c in content:
        text = getattr(c, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Coarse cost estimate in USD.

    Numbers reflect Haiku 4.5's list price at the time of writing — good
    enough for the budget guard and the report.
    """
    input_per_1m = 1.0
    output_per_1m = 5.0
    return (input_tokens * input_per_1m + output_tokens * output_per_1m) / 1_000_000
