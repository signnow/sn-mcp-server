"""LLM-based E2E tests for MCP tool selection validation.

Each test sends a natural-language prompt through a SmolAgents ToolCallingAgent
connected to the real sn-mcp serve subprocess via MCP STDIO, then asserts the
LLM selected the correct tool(s). All SignNow HTTP traffic hits a local mock
server — no real API calls.

Requires ``LLM_API_HOST``, ``LLM_MODEL``, ``LLM_KEY`` env vars.
Skipped (not failed) when those variables are absent.
"""

from __future__ import annotations

import pytest
from mcp import StdioServerParameters
from smolagents import OpenAIServerModel, ToolCallingAgent, ToolCollection

from tests.e2e.conftest import ToolCallAssertion, extract_tool_calls

SCENARIOS: list[tuple[str, str, ToolCallAssertion]] = [
    (
        "send_invite_to_document",
        "Send signing invite to document abc123 to user@example.com",
        ToolCallAssertion(
            expected_tools=["send_invite"],
            forbidden_tools=["send_invite_from_template", "create_from_template"],
        ),
    ),
    (
        "send_invite_from_template",
        "Send a signing invite from template tpl456 to user@example.com",
        ToolCallAssertion(
            expected_tools=["send_invite_from_template"],
            forbidden_tools=["create_from_template"],
        ),
    ),
    (
        "get_invite_status",
        "Get the status of the invite for document doc789",
        ToolCallAssertion(
            expected_tools=["get_invite_status"],
        ),
    ),
    (
        "list_documents_waiting",
        "List documents waiting for my signature",
        ToolCallAssertion(
            expected_tools=["list_documents"],
            forbidden_tools=["list_all_templates"],
        ),
    ),
    (
        "list_templates",
        "Show me all available templates",
        ToolCallAssertion(
            expected_tools=["list_all_templates"],
            forbidden_tools=["list_documents"],
        ),
    ),
    (
        "get_download_link",
        "Get a download link for document doc789",
        ToolCallAssertion(
            expected_tools=["get_document_download_link"],
            forbidden_tools=["get_signing_link"],
        ),
    ),
    (
        "create_from_template",
        "Create a new document from template tpl456",
        ToolCallAssertion(
            expected_tools=["create_from_template"],
            forbidden_tools=["send_invite_from_template"],
        ),
    ),
    (
        "embedded_sending",
        "Create an embedded sending link for document abc123",
        ToolCallAssertion(
            expected_tools=["create_embedded_sending"],
            forbidden_tools=["create_embedded_sending_from_template", "create_embedded_invite"],
        ),
    ),
]


@pytest.mark.e2e
@pytest.mark.parametrize(
    "scenario_id, prompt, assertion",
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS],
)
def test_tool_selection(
    mcp_server_params: StdioServerParameters,
    llm_model: OpenAIServerModel,
    scenario_id: str,
    prompt: str,
    assertion: ToolCallAssertion,
) -> None:
    """Run SmolAgents ToolCallingAgent and assert correct tool selection.

    Each test:
    1. Creates a ToolCollection from MCP STDIO connection
    2. Creates a ToolCallingAgent with max_steps=3
    3. Runs agent with the prompt
    4. Extracts tool_calls from agent memory
    5. Asserts expected/forbidden tools
    """
    with ToolCollection.from_mcp(mcp_server_params, trust_remote_code=True) as tool_collection:
        agent = ToolCallingAgent(
            tools=[*tool_collection.tools],
            model=llm_model,
            max_steps=3,
            add_base_tools=False,
        )
        agent.run(task=prompt)

        called_names = extract_tool_calls(agent)

        for name in assertion.expected_tools:
            assert name in called_names, f"Tool '{name}' expected but not called. Called: {called_names}. Prompt: '{prompt}'"

        for name in assertion.forbidden_tools:
            assert name not in called_names, f"Forbidden tool '{name}' was called. Called: {called_names}. Prompt: '{prompt}'"
