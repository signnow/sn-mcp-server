"""User-simulator strategies.

Two implementations of :class:`~eval.types.UserStrategy`:

- :class:`CannedUserStrategy` returns a fixed list of replies in order. This
  is the classic approach: cheap, deterministic, good for regression tests
  where the conversation pattern is stable.
- :class:`LLMUserStrategy` delegates each reply to a second Anthropic model
  that role-plays a user with a scripted goal. Used when the agent may ask
  clarifying questions that canned replies can't coherently answer.

Both are stateless from the runner's POV — the runner just hands in the
dialog history and receives the next reply (or ``None`` to stop).
"""

from __future__ import annotations

import os
from typing import Any


class CannedUserStrategy:
    """Returns a pre-scripted list of replies, one per call.

    Returns ``None`` once the script is exhausted so the driver knows to stop.
    The ``history`` argument is ignored — scripted replies don't react to
    what the agent actually said.
    """

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._idx = 0

    async def next_reply(self, _history: list[dict[str, str]]) -> str | None:
        if self._idx >= len(self._replies):
            return None
        reply = self._replies[self._idx]
        self._idx += 1
        return reply


class LLMUserStrategy:
    """LLM-driven user simulator with a scripted goal.

    The simulator's system prompt is built from ``goal_steps`` (ordered list
    of tasks the user is trying to accomplish) and ``constraints`` (things to
    refuse or require). Each turn, the harness's dialog history is passed in
    (with agent messages flipped to "user" and simulator's own past messages
    flipped to "assistant" — from the simulator LLM's POV it is the assistant
    replying, while the agent-under-test plays the part of "the human").

    The simulator signals end-of-conversation by replying with the literal
    token ``DONE``. The class also hard-caps its own turn count as a runaway
    guard — budget burn would compound otherwise.
    """

    def __init__(
        self,
        goal_steps: list[str],
        constraints: list[str] | None = None,
        simulator_model: str | None = None,
        max_tokens: int = 200,
        max_turns: int = 20,
    ) -> None:
        self.goal_steps = list(goal_steps)
        self.constraints = list(constraints or [])
        self.simulator_model = simulator_model or os.environ.get("EVAL_SIMULATOR_MODEL", "claude-haiku-4-5")
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        self._client: Any = None
        self._turns = 0

    async def next_reply(self, history: list[dict[str, str]]) -> str | None:
        if self._turns >= self.max_turns:
            return None

        # Skip the opening turn — it was written by the scenario author and
        # represents the initial_prompt the simulator is deemed to have "said"
        # to the agent. The simulator doesn't need to re-read it; its goals
        # live in the system prompt.
        conversation = history[1:] if history else []
        flipped: list[dict[str, str]] = []
        for h in conversation:
            content = h.get("content") or ""
            if not content:
                continue
            role = "user" if h.get("role") == "assistant" else "assistant"
            flipped.append({"role": role, "content": content})

        # Nothing to respond to yet — agent hasn't said anything. Let it run.
        if not flipped or flipped[-1]["role"] != "user":
            return None

        client = self._get_client()
        self._turns += 1
        response = await client.messages.create(
            model=self.simulator_model,
            max_tokens=self.max_tokens,
            system=self._build_system_prompt(),
            messages=flipped,
        )
        text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
        reply = "\n".join(getattr(b, "text", "") for b in text_blocks).strip()
        if not reply or reply.upper() == "DONE":
            return None
        return reply

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient
        except ImportError as err:  # pragma: no cover
            raise RuntimeError("LLMUserStrategy requires the 'anthropic' package. Install with: pip install anthropic") from err
        base_url = os.environ.get("LITELLM_BASE_URL")
        api_key = os.environ.get("LITELLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("LLMUserStrategy requires LITELLM_API_KEY or ANTHROPIC_API_KEY in env")
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "http_client": DefaultAsyncHttpxClient(),
        }
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**kwargs)
        return self._client

    def _build_system_prompt(self) -> str:
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(self.goal_steps))
        cons = "\n".join(f"  - {c}" for c in self.constraints) if self.constraints else "  (none)"
        return (
            "You are role-playing a SignNow end-user working with a signing "
            "assistant. Your job is to drive the assistant toward the goals "
            "below, reply briefly to its questions, and stop when everything "
            "is done.\n\n"
            f"Goals (pursue in order):\n{steps}\n\n"
            f"Constraints:\n{cons}\n\n"
            "Rules:\n"
            "  - Stay in character as the user. Never act as the assistant.\n"
            "  - Keep replies short — one sentence unless clarification requires more.\n"
            "  - Do not invent tasks beyond the goals above.\n"
            "  - If the assistant offers a step not in your goals (e.g. preview), "
            "decline politely.\n"
            "  - When every goal has been completed, reply with the single token "
            "'DONE' and nothing else."
        )
