"""E2E tests for the signnow_skills MCP tool.

Verifies two behaviours through a full SmolAgents → MCP-STDIO round-trip:

1. Listing skills: the agent calls ``signnow_skills`` with no arguments and its
   final answer mentions the names of available skills (at minimum "signnow101").

2. Fetching a skill by name: the agent calls ``signnow_skills(skill_name="signnow101")``
   and its final answer contains text from the skill body ("Entity Types Glossary").

Skipped when LLM_API_HOST / LLM_MODEL / LLM_KEY env vars are absent (same rule
as the rest of the E2E suite — see conftest.py).
"""

from __future__ import annotations

import pytest
from mcp import StdioServerParameters
from smolagents import OpenAIServerModel, ToolCallingAgent, ToolCollection

from tests.e2e.conftest import extract_tool_calls

SKILL_TOOL = "signnow_skills"
KNOWN_SKILL_NAME = "signnow101"
# Unique phrase that only appears in the signnow101 skill body (not in its description)
SKILL_BODY_MARKER = "Entity Types Glossary"


@pytest.mark.e2e
def test_skills_list_returns_available_skills(
    mcp_server_params: StdioServerParameters,
    llm_model: OpenAIServerModel,
) -> None:
    """Agent calls signnow_skills and its answer names the available skills."""
    with ToolCollection.from_mcp(mcp_server_params, trust_remote_code=True) as tool_collection:
        agent = ToolCallingAgent(
            tools=[*tool_collection.tools],
            model=llm_model,
            max_steps=3,
            add_base_tools=False,
        )
        answer = agent.run("List all available SignNow skills.")

        called = extract_tool_calls(agent)
        assert SKILL_TOOL in called, f"Expected '{SKILL_TOOL}' to be called for a skill-listing prompt, but called tools were: {called}"
        assert KNOWN_SKILL_NAME in str(answer), f"Expected skill name '{KNOWN_SKILL_NAME}' to appear in the agent answer, but got: {answer!r}"


@pytest.mark.e2e
def test_skills_get_returns_skill_body(
    mcp_server_params: StdioServerParameters,
    llm_model: OpenAIServerModel,
) -> None:
    """Agent calls signnow_skills(skill_name='signnow101') and answer contains skill body text."""
    with ToolCollection.from_mcp(mcp_server_params, trust_remote_code=True) as tool_collection:
        agent = ToolCallingAgent(
            tools=[*tool_collection.tools],
            model=llm_model,
            max_steps=3,
            add_base_tools=False,
        )
        answer = agent.run(f"Retrieve the full content of the '{KNOWN_SKILL_NAME}' skill.")

        called = extract_tool_calls(agent)
        assert SKILL_TOOL in called, f"Expected '{SKILL_TOOL}' to be called when fetching a named skill, but called tools were: {called}"
        assert SKILL_BODY_MARKER in str(answer), f"Expected skill body marker '{SKILL_BODY_MARKER}' in the agent answer, but got: {answer!r}"
