"""E2E test fixtures for LLM-based tool selection validation.

Provides mock SignNow HTTP server, SmolAgents agent fixtures, and skip
logic for when LLM API credentials are not configured.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Snapshot env vars BEFORE any third-party import — smolagents eagerly loads
# python-dotenv which injects .env values into os.environ. The skip logic
# must check the pre-import state to detect genuinely missing credentials
# (CI, clean env) vs locally-configured .env files.
# ---------------------------------------------------------------------------
_REQUIRED_ENV = {"LLM_API_HOST", "LLM_MODEL", "LLM_KEY"}
_MISSING_AT_STARTUP = _REQUIRED_ENV - set(os.environ)

import re  # noqa: E402
from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from mcp import StdioServerParameters  # noqa: E402
from pydantic import BaseModel, ValidationInfo, field_validator  # noqa: E402
from pytest_httpserver import HTTPServer  # noqa: E402
from smolagents import ActionStep, OpenAIServerModel, ToolCallingAgent  # noqa: E402

# ---------------------------------------------------------------------------
# Skip logic — autouse session fixture
# ---------------------------------------------------------------------------
# DO NOT use pytest.skip(allow_module_level=True) in conftest.py — it raises
# Skipped during conftest collection, which pytest converts to ERROR (exit 1).
# The autouse fixture approach produces exit code 0 and SKIPPED status.


@pytest.fixture(scope="session", autouse=True)
def require_llm_env() -> None:
    """Skip the entire E2E suite when LLM env vars are not set."""
    if _MISSING_AT_STARTUP:
        pytest.skip(f"LLM API not configured: {', '.join(sorted(_MISSING_AT_STARTUP))} not set")


# ---------------------------------------------------------------------------
# Assertion model
# ---------------------------------------------------------------------------


class ToolCallAssertion(BaseModel):
    """Defines expected tool call behavior for a single test scenario."""

    expected_tools: list[str]
    """Tool names that MUST appear in tool_calls (order ignored)."""

    forbidden_tools: list[str] = []
    """Tool names that MUST NOT appear in tool_calls."""

    @field_validator("expected_tools")
    @classmethod
    def at_least_one_expected(cls, v: list[str]) -> list[str]:
        """Require at least one expected tool to avoid vacuous tests."""
        if not v:
            raise ValueError("expected_tools must not be empty")  # noqa: TRY003
        return v

    @field_validator("forbidden_tools")
    @classmethod
    def no_overlap_with_expected(cls, v: list[str], info: ValidationInfo) -> list[str]:
        """Prevent a tool from being both expected and forbidden."""
        expected: list[str] = info.data.get("expected_tools", [])
        overlap = set(v) & set(expected)
        if overlap:
            msg = f"Tools in both expected and forbidden: {overlap}"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def extract_tool_calls(agent: ToolCallingAgent) -> list[str]:
    """Extract all tool names the LLM attempted to call during an agent run.

    Checks two sources per ``ActionStep``:

    1. ``step.tool_calls`` — successfully executed tool calls.
    2. ``step.model_output_message.tool_calls`` — raw LLM-requested tool calls
       (includes calls that smolagents rejected due to argument type validation,
       e.g. ``null`` for a ``string`` param).

    This dual-source approach is necessary because smolagents' ``anyOf`` schema
    handling can reject valid optional-parameter patterns (``str | None``),
    causing the tool call to fail validation even though the LLM selected the
    correct tool.

    Returns deduplicated list preserving first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []

    def _add(name: str) -> None:
        if name not in seen:
            result.append(name)
            seen.add(name)

    for step in agent.memory.steps:
        if not isinstance(step, ActionStep):
            continue
        # 1. Successfully executed tool calls
        if step.tool_calls is not None:
            for tc in step.tool_calls:
                _add(tc.name)
        # 2. Raw LLM-requested tool calls (may include rejected ones)
        msg = step.model_output_message
        if msg is not None and msg.tool_calls is not None:
            for tc in msg.tool_calls:
                _add(tc.function.name)
    return result


# ---------------------------------------------------------------------------
# Mock HTTP server
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mock_signnow_server() -> Generator[HTTPServer, None, None]:
    """Start a mock HTTP server intercepting all SignNow API traffic.

    Routes registered in specificity order (first match wins):
    1. POST /oauth2/token → fake bearer token
    2. GET /user/documentsv2 → paginated doc list (for list_documents)
    3. GET /document/{id}/field-invite → invite status list (for get_invite_status)
    4. Catch-all /.* → generic ``{"id": "mock-id", "status": "success"}``
    """
    server = HTTPServer(host="127.0.0.1")

    # 1. OAuth token endpoint (most specific — POST only)
    server.expect_request("/oauth2/token", method="POST").respond_with_json(
        {"access_token": "fake-token", "token_type": "Bearer", "expires_in": 3600},  # noqa: S105
    )

    # 2. Structured-response routes (before catch-all)
    server.expect_request(re.compile(r"/user/documentsv2.*")).respond_with_json(
        {"data": [{"id": "mock-doc-id", "document_name": "Test Document"}], "total_pages": 1},
    )
    server.expect_request(re.compile(r"/document/.+/field-invite")).respond_with_json(
        [{"id": "mock-invite-id", "status": "pending", "email": "user@example.com", "role": "Signer"}],
    )

    # 3. Catch-all — minimal shape for tools where only presence-of-call matters
    server.expect_request(re.compile("/.*")).respond_with_json(
        {"id": "mock-id", "status": "success"},
    )

    server.start()
    yield server
    server.clear()
    server.stop()


# ---------------------------------------------------------------------------
# Subprocess environment
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mcp_server_env(mock_signnow_server: HTTPServer) -> dict[str, str]:
    """Build environment dict for the sn-mcp serve subprocess.

    Starts from ``os.environ.copy()`` — ``StdioServerParameters.env`` REPLACES
    (not inherits) the subprocess env, so copying ensures portability across
    virtualenvs, conda, SSL proxies, and locale-sensitive systems.
    """
    env = os.environ.copy()
    env["SIGNNOW_API_BASE"] = f"http://127.0.0.1:{mock_signnow_server.port}"
    env["SIGNNOW_USER_EMAIL"] = "test@example.com"
    env["SIGNNOW_PASSWORD"] = "fake-password"  # noqa: S105
    env["SIGNNOW_API_BASIC_TOKEN"] = "fake-basic-token"  # noqa: S105
    return env


@pytest.fixture(scope="session")
def mcp_server_params(mcp_server_env: dict[str, str]) -> StdioServerParameters:
    """Create ``StdioServerParameters`` for ``sn-mcp serve``."""
    return StdioServerParameters(
        command="sn-mcp",
        args=["serve"],
        env=mcp_server_env,
    )


# ---------------------------------------------------------------------------
# LLM model
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def llm_model() -> OpenAIServerModel:
    """Create SmolAgents LLM model from env vars.

    Sets ``temperature=0`` for deterministic tool selection — primary
    mitigation for LLM non-determinism (see spec Section 7).
    """
    return OpenAIServerModel(
        model_id=os.environ["LLM_MODEL"],
        api_base=os.environ["LLM_API_HOST"],
        api_key=os.environ["LLM_KEY"],
        temperature=0,
    )
