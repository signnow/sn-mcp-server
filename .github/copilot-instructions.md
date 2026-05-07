# Copilot Instructions for AI Coding Agents

> **Full governance document:** `AGENTS.md` — read it before making architectural decisions.

## 1. Project Overview

**SignNow MCP Server** is a *stateless translation layer* between AI agents and the SignNow eSignature REST API, built on the **Model Context Protocol (MCP)**. It receives MCP tool calls, translates them into SignNow API requests, and returns minimal, token-efficient responses. It holds no state, stores no data, and caches nothing.

**Key principle — "The Thin Translator":** Every design decision must reinforce statelessness, token efficiency, and minimal tool surface. Never return raw SignNow API responses; always curate through `tools/models.py`.

**Source layout:**
```
src/
├── sn_mcp_server/     # MCP server: CLI, auth, tools, HTTP app
└── signnow_client/    # SignNow API client: HTTP methods, models, exceptions
tests/unit/            # Unit tests — mirrors src/ structure (no network calls)
examples/              # LangChain / LlamaIndex / SmolAgents integration demos
```

## 2. Technology Stack

| Component | Library / Version |
|-----------|------------------|
| MCP framework | `fastmcp >= 2.13, < 3` |
| HTTP app | `starlette >= 0.27` + `uvicorn` |
| CLI | `typer >= 0.9` |
| HTTP client | `httpx[http2] >= 0.25` |
| Auth | `pyjwt[crypto]` + `cryptography >= 42` |
| Models / config | `pydantic >= 2.0` + `pydantic-settings >= 2.0` |
| Testing | `pytest` + `pytest-asyncio` + `pytest-mock` |
| Linting | `ruff` (line length 200) |
| Formatting | `black` (line length 200, target py310) |
| Type checking | `mypy --strict` |

## 3. Build, Lint & Test Commands

```bash
# Install (editable)
pip install -e .

# Run all unit tests
pytest tests/unit/ -v

# Lint
ruff check src/ tests/

# Format check
ruff format --check src/ tests/

# Type check
mypy src/

# Run HTTP server locally (default: 127.0.0.1:8000)
make up
# or
pip install -e . && sn-mcp http

# Run via Docker
docker compose up
```

> All three commands (`pytest`, `ruff check`, `ruff format --check`) must pass before committing.

## 4. Architecture Layers

```
AI Agent
  │ STDIO / Streamable HTTP / SSE
  ▼
Transport Layer  (cli.py → serve/http, app.py → Starlette + FastMCP)
  ▼
Auth Layer       (token_provider.py — 3 strategies, auth.py — OAuth2/JWT/JWKS)
  ▼
MCP Tool Layer   (tools/signnow.py — orchestrators, tools/<feature>.py — logic)
  ▼
API Client Layer (signnow_client/client.py — mixin-based httpx wrapper)
  ▼
SignNow REST API
```

**Layer access rules (no upward imports):**
- Tools may use `signnow_client` and `token_provider` — never Starlette objects.
- `signnow_client` must never import from `sn_mcp_server`.
- Tool business logic (`tools/<feature>.py`) must be injectable with a mocked client for unit tests.

## 5. Authentication Resolution Order

```
1. Config credentials (email + password + basic_token) → password grant
2. HTTP Bearer header present → extract and use directly
3. OAuth2 flow (client_id + client_secret + RSA key) → JWT token exchange
4. None available → raise error: "No authentication method available"
```

## 6. Adding a New MCP Tool

1. Create `src/sn_mcp_server/tools/<feature>.py` with pure business logic.
2. Add a curated response model to `src/sn_mcp_server/tools/models.py`.
3. Register the tool in `src/sn_mcp_server/tools/__init__.py` → `register_tools()`.
4. Add the `@mcp.tool` decorated function in `src/sn_mcp_server/tools/signnow.py`.
5. Write unit tests in `tests/unit/sn_mcp_server/tools/test_<feature>.py`.
6. Add the tool to the Tools section of `README.md`.

## 7. Development Rules

- **Curated responses only.** Never return raw SignNow API JSON — always go through `tools/models.py`.
- **Specific errors always.** Every error must state the operation, entity (with IDs), and cause.
- **No generic catch-alls.** Never return "Something went wrong" — return HTTP status + SignNow error body.
- **Stateless.** No module-level mutable state, no global caches, no singletons holding request data.
- **No secrets in output.** Tokens, passwords, API keys must never appear in logs, errors, or tool responses.
- **No network in unit tests.** All `httpx` calls must be mocked in `tests/unit/`.
- **YAGNI.** Don't add functionality until it's actually needed. No "just in case" abstractions.
- **Minimize tools.** Combine document and document-group operations into one tool — the tool decides which API path internally.

## 8. Forbidden Anti-Patterns

- ❌ Raw API passthrough (return unfiltered SignNow responses)
- ❌ Upward imports (`signnow_client` importing from `sn_mcp_server`)
- ❌ Transport in tools (importing Starlette or reading HTTP headers in tool functions)
- ❌ State leakage (module-level mutable state between requests)
- ❌ Secrets in output (tokens, passwords, PEM content in any log or response)
- ❌ Network calls in unit tests (no real API requests in CI)
- ❌ Orphan tools (every tool must be registered in `__init__.py` and in `README.md`)
- ❌ Vague errors (`"Error occurred"`, `"Request failed"`, bare exception messages)
- ❌ Infrastructure coupling (no AWS/GCP/Azure-specific code or hardcoded hostnames)

## 9. Critical Files

| File | Purpose |
|------|---------|
| `src/sn_mcp_server/app.py` | Starlette HTTP app + middleware stack |
| `src/sn_mcp_server/server.py` | FastMCP server factory |
| `src/sn_mcp_server/cli.py` | CLI entry points (`serve`, `http`) |
| `src/sn_mcp_server/config.py` | Server/OAuth settings (pydantic-settings) |
| `src/sn_mcp_server/auth.py` | OAuth2 endpoints, JWT, JWKS |
| `src/sn_mcp_server/token_provider.py` | Token resolution (3 auth strategies) |
| `src/sn_mcp_server/tools/__init__.py` | `register_tools()` — tool registration hub |
| `src/sn_mcp_server/tools/signnow.py` | MCP tool definitions (thin orchestrators) |
| `src/sn_mcp_server/tools/models.py` | Curated response models for tools |
| `src/signnow_client/client.py` | Composed client (mixin aggregation) |
| `src/signnow_client/client_base.py` | Base HTTP methods + error handling |
| `src/signnow_client/exceptions.py` | Typed exception hierarchy |
| `pyproject.toml` | Dependencies, build config — **do not modify without explicit request** |
| `pytest.ini` | Test config — **do not modify without explicit request** |
| `AGENTS.md` | Full architectural governance document |

## 10. Code Style

- **Line length:** 200 characters (black + ruff)
- **Python target:** 3.10+
- **Imports:** isort-ordered via ruff (`I` rule set)
- **Type annotations:** required on all function signatures (`mypy --strict`)
- **Pydantic models:** use `model_config = ConfigDict(...)` (v2 style, no `class Config`)
- **Async:** use `async def` + `await` for all tool functions; use `pytest-asyncio` in tests

---

For full architectural governance, constraints, and detailed patterns, read `AGENTS.md`.