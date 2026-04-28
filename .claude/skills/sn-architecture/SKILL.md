---
name: sn-architecture
description: >
  SignNow MCP Server architecture rules, layer constraints, and design philosophy.
  Use when working on any source code in this project — implementing features, reviewing code,
  writing specs, planning, or testing. Covers the Thin Translator philosophy, stateless design,
  layer access matrix, dependency rules, and known gotchas. Do NOT use for git commits
  or documentation-only tasks.
---

# SignNow MCP Server — Architecture

## Identity

This server is a **stateless translation layer** between AI agents and the SignNow API. It adds zero noise and carries only the signal the agent needs. Every design decision reinforces this identity.

## Guiding Principles

| Principle | Rule |
|-----------|------|
| **Thin Translator** | Zero state, zero caching, zero business logic that belongs in the agent. |
| **Stateless** | No in-memory state between requests, no session objects, no module-level mutable state, no singletons. |
| **Tool Minimization** | Fewer tools with broader capability. One tool decides internally whether to call document vs. document-group API. |
| **Token Efficiency** | Every field in a response costs money and context. Carry only the minimum data the agent needs for its next decision. Omit nulls, empty lists, metadata. |
| **Testability** | Every business logic function is unit-testable by injecting a mocked `SignNowAPIClient`. If a design makes testing harder, the design is wrong. |
| **Specific Errors** | Every error message names the operation, entity (with IDs), and cause. |
| **YAGNI** | Don't add functionality until it's actually needed. No future-proofing for hypothetical requirements. |
| **No Infrastructure Coupling** | No AWS/GCP/Azure assumptions. |

## Layer Architecture

```
Agent Request
  → Transport (Starlette / STDIO / SSE)
    → Tool Orchestrator (tools/signnow.py)
      → Token Resolution (TokenProvider)
        → Business Logic (tools/<feature>.py)
          → API Client (signnow_client/client_*.py)
            → SignNow API
              → Response Model (tools/models.py)
                → Agent
```

### Layer Definitions & Access Rules

| # | Layer | Location | May Import | Must NOT Import |
|---|-------|----------|------------|-----------------|
| 1 | **API Models** | `signnow_client/models/` | `pydantic` only | `sn_mcp_server.*`, `signnow_client/client*.py` |
| 2 | **API Client** | `signnow_client/client_*.py` | Layer 1, `signnow_client/exceptions.py`, `httpx` (via base class) | `sn_mcp_server.*` (NO upward imports) |
| 3 | **Tool Response Models** | `sn_mcp_server/tools/models.py` | `pydantic`, Layer 1 types (for references) | Raw API passthrough |
| 4 | **Tool Business Logic** | `sn_mcp_server/tools/<feature>.py` | Layer 2 (client), Layer 3 (models) | Starlette, other tool modules, token resolution |
| 5 | **Tool Orchestrator** | `sn_mcp_server/tools/signnow.py` | Layer 4, `TokenProvider` | Business logic in orchestrator body |
| 6 | **Auth** | `sn_mcp_server/auth.py`, `token_provider.py` | `signnow_client`, config | Tools layer |
| 7 | **Transport** | `sn_mcp_server/app.py`, `cli.py` | `server.py`, `config.py`, `auth.py` | Tools directly, API client directly |

### The One Rule That Matters Most

**Dependency arrow is strictly downward:** `sn_mcp_server → signnow_client`. Never the reverse. Any import from `sn_mcp_server` inside `signnow_client` is an immediate reject.

## Key Patterns

### Token Flow

Token resolution belongs in the orchestrator (`tools/signnow.py`) via `_get_token_and_client()`. Business logic functions receive `token: str` as a parameter — they never resolve tokens themselves.

### Response Curation

Every API response goes through `tools/models.py`. Never return raw SignNow JSON. Each field must justify: "Does the agent need this for its next decision?" If no — omit.

### Error Handling

```python
# ✅ Specific — operation + entity + cause
raise ValueError(f"Cannot send invite for document '{document_id}': no signers configured")

# ❌ Vague — no context
raise ValueError("Something went wrong")
```

### Secrets

Tokens, passwords, API keys, PEM content must NEVER appear in logs, errors, or tool responses. Use `_mask_secret_value()` for diagnostic output.

### Tool Registration

Every tool must be registered in `tools/__init__.py` → `register_tools()` and documented in `README.md`.

## Gotchas

- **auth.py module-level side effects.** Importing `auth.py` triggers config load → RSA keygen → stdout print → client creation. In tests, mock or avoid importing directly.
- **No token caching.** Password grant fires a network call on EVERY tool invocation.
- **RSA key regenerated silently** if `OAUTH_RSA_PRIVATE_KEY` PEM is missing — invalidates all JWTs.
- **`.env` read from CWD**, not project root.
- **Empty env vars become defaults silently.** `OAUTH_ISSUER=""` → `http://localhost:8000`.
- **Middleware order matters.** Starlette wraps LIFO: Bearer → TrailingSlash → CORS → App.
- **BearerJWT middleware bypassed in password-grant mode.**
- **Both `/sse` and `/mcp` mounted.** Legacy SSE + modern Streamable HTTP.
- **`redirect_target` exclusion.** Request models drop `redirect_target` when `redirect_uri` is absent.

## Sacred Files

Do NOT modify without explicit instruction: `pyproject.toml`, `pytest.ini`, `AGENTS.md`.

## Reference Docs

- `AGENTS.md` — project governance constitution
- `ARCHITECTURE.md` — authoritative architectural specification
