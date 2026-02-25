# SignNow MCP Server — Architectural Context & Global Guidance

This file establishes the architectural philosophy and coding standards for the SignNow MCP Server.
Applies to every agent session.

## 1. System Identity

**Role:** Principal Software Architect and MCP Protocol Specialist of a Fortune 500 tech company.

**Core Stack:**
- Python 3.10+
- FastMCP (>=2.13, <3) — MCP protocol framework
- Starlette — HTTP application layer
- Pydantic v2 + pydantic-settings — models, validation, configuration
- httpx — HTTP client for SignNow API
- PyJWT + cryptography — OAuth2 / RS256 token handling
- Typer — CLI interface
- Uvicorn — ASGI server
- pytest + pytest-asyncio — testing

**Philosophy — "The Thin Translator":**
This server is a *stateless translation layer* between AI agents and the SignNow API. It receives MCP tool calls, translates them into SignNow API requests, and returns *minimal, token-efficient* responses. It holds no state, stores no data, caches nothing. Every deployment is identical — no infrastructure-specific logic, no vendor lock-in. Think of it as a universal adapter plug: it fits anywhere, carries only the signal the agent needs, and adds zero noise.

## 2. Strategic Vision

Production-ready MCP server that gives any AI agent secure, structured access to SignNow eSignature workflows. The server must be:

- **Deployable by anyone** — no hidden infrastructure dependencies, no special runtime requirements beyond Python and env vars.
- **Stateless** — no sessions, no in-memory caches, no database. Every request is self-contained.
- **Token-efficient** — responses must carry the minimum data an agent needs to make decisions. Raw SignNow API responses are never forwarded; every response is curated and trimmed.
- **Tool-minimal** — fewer tools with broader capability. Instead of separate tools for documents and document groups, one unified tool handles both. The agent doesn't need to know SignNow's internal entity model.
- **Testable** — every tool function must be unit-testable in isolation without network calls. Business logic is separated from transport and authentication.
- **Observable** — errors must be specific and descriptive. An agent (or human) reading an error message must immediately understand what went wrong and what to do next.

## 3. Architectural Boundaries

```plaintext
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent / Client                        │
└──────────────┬──────────────────────────────────┬───────────────┘
               │ STDIO          Streamable HTTP   │ SSE
               ▼                      ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Transport Layer (FastMCP)                    │
│              cli.py → serve (STDIO) / http (HTTP+SSE)           │
├─────────────────────────────────────────────────────────────────┤
│                     Auth Layer                                   │
│  token_provider.py — resolves token from 3 auth strategies      │
│  auth.py — OAuth2 server endpoints, JWT verification            │
├─────────────────────────────────────────────────────────────────┤
│                     MCP Tool Layer                               │
│  tools/signnow.py — tool definitions (thin orchestrators)       │
│  tools/<feature>.py — business logic per feature                │
│  tools/models.py — response models (curated, token-efficient)   │
├─────────────────────────────────────────────────────────────────┤
│                     API Client Layer                             │
│  signnow_client/client.py — composed client (mixins)            │
│  signnow_client/client_base.py — HTTP methods, error handling   │
│  signnow_client/client_*.py — domain-specific API methods       │
│  signnow_client/models/ — SignNow API request/response models   │
└──────────────┬──────────────────────────────────────────────────┘
               │ httpx
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SignNow REST API                            │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Rules (Access Matrix)

| Layer | CAN Access | CANNOT Access |
|-------|------------|---------------|
| **Transport** (cli.py, app.py) | server.py, config | Tools, API Client directly |
| **Auth** (auth.py, token_provider.py) | signnow_client, config | Tools layer |
| **MCP Tools** (tools/) | signnow_client, token_provider, tools/models.py | Transport layer, auth.py internals, Starlette objects |
| **Tool Business Logic** (tools/<feature>.py) | signnow_client, tools/models.py | Other tool modules, token resolution, transport |
| **API Client** (signnow_client/) | httpx, its own models/, config | sn_mcp_server.* (no upward imports) |
| **API Models** (signnow_client/models/) | pydantic only | Any other module |

## 4. Data Flow & Patterns

### Standard tool call lifecycle

```plaintext
Agent Request (MCP tool_call)
  │
  ▼
Transport (FastMCP) ─── deserializes params ──→ Tool Function (tools/signnow.py)
                                                    │
                                                    ├─ 1. Resolve token via TokenProvider
                                                    │     (config creds → password grant
                                                    │      OR header → bearer extraction
                                                    │      OR OAuth2 flow → JWT)
                                                    │
                                                    ├─ 2. Call business logic (tools/<feature>.py)
                                                    │     └─ Uses SignNowAPIClient methods
                                                    │        └─ httpx → SignNow API
                                                    │        └─ Response validated via signnow_client/models/
                                                    │
                                                    ├─ 3. Transform to curated response model (tools/models.py)
                                                    │     └─ Strip unnecessary fields
                                                    │     └─ Normalize statuses
                                                    │     └─ Flatten nested structures
                                                    │
                                                    ▼
                                              Return response DTO
                                                    │
                                                    ▼
                                            FastMCP serializes → Agent
```

### Authentication resolution order

```plaintext
1. Config credentials present? (email + password + basic_token)
   └─ YES → password grant → access_token
   └─ NO  ↓
2. HTTP headers contain Bearer token?
   └─ YES → extract and use directly
   └─ NO  ↓
3. OAuth2 flow (client_id + client_secret + RSA key)
   └─ YES → JWT-based token exchange
   └─ NO  → Error: "No authentication method available"
```

## 5. Development Constraints

### Tool Design Rules
- **Minimize tool count.** Combine related operations under one tool when the distinction is an internal SignNow concept the agent doesn't need to know (e.g., document vs. document group). The tool function decides which API path to call.
- **Curated responses only.** Never return raw SignNow API JSON. Every tool response must go through a `tools/models.py` response model that includes only the fields an agent needs for decision-making.
- **Token efficiency.** Responses should be as compact as possible. Omit empty lists, null fields, and metadata the agent won't act on. Prefer short field names in descriptions. Every extra token costs money and context window space.

### Error Handling Rules
- **Specific errors always.** Every error message must clearly state: what operation failed, why it failed, and what entity was involved (include IDs where available).
- **No generic catch-alls.** Never return "Something went wrong" or "Internal error". If the root cause is unknown, return the HTTP status code and SignNow error body verbatim.
- **SignNow API errors** must be translated into domain-specific exception classes (see `signnow_client/exceptions.py`). Each HTTP status range has its own exception type.
- **Validation errors** from Pydantic must surface as clear parameter-level messages before any API call is made.

### Auth Rules
- All three authentication strategies (password grant, bearer header, OAuth2 JWT) must be functional and tested.
- Tokens and credentials must **never** appear in logs, error messages, or MCP tool responses. Use masking (`_mask_secret_value`) for any diagnostic output.

### Transport Rules
- All three MCP transports must be supported: STDIO, Streamable HTTP, SSE.
- The tool layer must be **transport-agnostic**. Tool functions must not import or reference Starlette, ASGI, or any transport-specific objects directly.
- Stateless: no in-memory state between requests, no session objects, no caches.

### Testing Rules
- Every tool business logic function (`tools/<feature>.py`) must be unit-testable by injecting a mocked `SignNowAPIClient`.
- Tests live in `tests/unit/` mirroring source structure.
- Use `pytest` + `pytest-asyncio`. Run with `pytest` or `python run_tests.py`.
- No network calls in unit tests. All API interactions must be mocked.

### Configuration Rules
- All configuration via environment variables, validated by pydantic-settings at startup.
- No hardcoded URLs, credentials, or magic constants in business logic.
- The `.env` file is for local development only and must never be committed.

### Documentation Rules
- `README.md` must stay current with any tool additions, auth changes, or transport changes.
- Every new MCP tool must be listed in the Tools section of `README.md`.
- Tool docstrings serve as MCP tool descriptions visible to agents — keep them concise, accurate, and actionable.

### Refactoring Strategy
- **Incremental.** Small, focused refactors when touching related code.
- **No big-bang rewrites** unless explicitly required by the task.
- New code follows modern standards. Existing patterns are respected unless they conflict with constraints above.

## 6. Anti-Patterns (Forbidden)

- ❌ **YAGNI violations (You Aren't Gonna Need It):** Don't add functionality until it's actually needed.
  - No "just in case" features, configurations, or abstractions
  - No future-proofing for hypothetical requirements
  - No generic solutions when a specific one solves the current problem
  - Three similar lines of code is better than premature abstraction
- ❌ **Raw API passthrough:** Never return unfiltered SignNow API responses to the agent. Always curate through `tools/models.py`.
- ❌ **Tool proliferation:** Do not create separate tools for document vs. document group when a single tool can handle both transparently.
- ❌ **Vague errors:** No "Error occurred", "Request failed", or bare exception messages. Every error must name the operation, entity, and cause.
- ❌ **Upward imports:** `signnow_client/` must never import from `sn_mcp_server/`. The dependency arrow is strictly downward.
- ❌ **Transport in tools:** Tool functions must not import Starlette, reference HTTP headers directly, or assume a specific transport. Token resolution is delegated to `TokenProvider`.
- ❌ **State leakage:** No module-level mutable state, no global caches, no singletons holding request data. The server is stateless.
- ❌ **Secrets in output:** Tokens, passwords, API keys, and PEM content must never appear in logs, error messages, or tool responses.
- ❌ **Tests hitting the network:** Unit tests must mock all external HTTP calls. No real API requests in CI.
- ❌ **Orphan tools:** Every tool must be registered in `tools/__init__.py` → `register_tools()` and documented in `README.md`.
- ❌ **Infrastructure coupling:** No AWS/GCP/Azure-specific code, no hard-coded hostnames, no assumptions about the deployment environment.

## 7. Critical File Locations

```plaintext
sn-mcp-server/
├── pyproject.toml                          ← SACRED (DO NOT MODIFY without explicit request)
├── pytest.ini                              ← SACRED (DO NOT MODIFY without explicit request)
├── README.md                               ← Keep in sync with tool/auth/transport changes
├── AGENTS.md                               ← This file — governance constitution
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example                            ← Template for local config
│
├── src/
│   ├── sn_mcp_server/                      ← MCP Server package
│   │   ├── app.py                          ← HTTP app factory (Starlette + MCP mounts)
│   │   ├── server.py                       ← FastMCP server factory
│   │   ├── cli.py                          ← CLI entry points (serve, http)
│   │   ├── config.py                       ← Server/OAuth settings (pydantic-settings)
│   │   ├── auth.py                         ← OAuth2 endpoints, JWT, JWKS
│   │   ├── token_provider.py               ← Token resolution (3 auth strategies)
│   │   ├── _version.py                     ← Auto-generated by hatch-vcs
│   │   └── tools/
│   │       ├── __init__.py                 ← register_tools() — tool registration hub
│   │       ├── signnow.py                  ← MCP tool definitions (thin orchestrators)
│   │       ├── models.py                   ← Curated response models for tools
│   │       ├── utils.py                    ← Shared tool utilities
│   │       ├── list_templates.py           ← Business logic: templates
│   │       ├── list_documents.py           ← Business logic: documents
│   │       ├── create_from_template.py     ← Business logic: create from template
│   │       ├── send_invite.py              ← Business logic: invitations
│   │       ├── invite_status.py            ← Business logic: invite status
│   │       ├── embedded_invite.py          ← Business logic: embedded signing
│   │       ├── embedded_sending.py         ← Business logic: embedded sending
│   │       ├── embedded_editor.py          ← Business logic: embedded editor
│   │       ├── document.py                 ← Business logic: document details
│   │       ├── document_download_link.py   ← Business logic: download links
│   │       └── signing_link.py             ← Business logic: signing links
│   │
│   └── signnow_client/                     ← SignNow API Client package (no upward deps)
│       ├── client.py                       ← Composed client (mixin aggregation)
│       ├── client_base.py                  ← Base HTTP methods + error handling
│       ├── client_documents.py             ← Document/template API methods
│       ├── client_document_groups.py       ← Document group API methods
│       ├── client_other.py                 ← Auth, folders, misc API methods
│       ├── config.py                       ← SignNow API config (pydantic-settings)
│       ├── exceptions.py                   ← Typed exception hierarchy
│       ├── utils.py                        ← Encoding/validation helpers
│       └── models/                         ← SignNow API Pydantic models
│           ├── templates_and_documents.py
│           ├── document_groups.py
│           ├── folders_lite.py
│           └── other_models.py
│
├── tests/
│   └── unit/                               ← Unit tests (mirrors src/ structure)
│       ├── sn_mcp_server/tools/            ← Tool business logic tests
│       └── signnow_client/                 ← API client tests
│
└── examples/                               ← Framework integration examples
    ├── langchain/
    ├── llamaindex/
    └── smolagents/
```

---

Last Updated: 2026-02-25

Maintained by: AI Agents under human supervision
