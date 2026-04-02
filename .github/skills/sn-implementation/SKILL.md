---
name: sn-implementation
description: >
  Coding standards and implementation patterns for SignNow MCP Server. Use when writing
  or modifying Python source code in this project — implementing features, fixing bugs,
  refactoring. Covers layer-specific coding rules, error handling patterns, typing standards,
  the bug fix protocol, and verification steps. Do NOT use for spec writing, planning,
  or test authoring — those have dedicated skills.
---

# Implementation Standards

## Layer-Specific Rules

Before writing any code, identify the layer you're editing and apply its rules.

### API Models (`signnow_client/models/`)

- ✅ Pydantic `BaseModel`, `Field`, validators, type aliases, `__all__` exports.
- ❌ Imports from `sn_mcp_server.*` or `signnow_client/client*.py`. Any business logic.
- Pure data definitions only — mirror the SignNow REST API schema.

### API Client (`signnow_client/client_*.py`)

- ✅ Use `self._get()`, `self._post()`, `self._put()`, `self._post_multipart()` from `client_base.py`. Import models from `signnow_client/models/`. Use exceptions from `signnow_client/exceptions.py`.
- ❌ Imports from `sn_mcp_server.*` (upward import). Direct `httpx` calls. Starlette imports. MCP logic.
- Each method takes `token: str` and passes `Authorization: Bearer {token}`.

### Tool Response Models (`sn_mcp_server/tools/models.py`)

- ✅ Pydantic `BaseModel`, `Field`. Type references from `signnow_client/models/`.
- ❌ Raw API passthrough. Fields the agent won't act on. Empty lists, null metadata, internal IDs.
- Every field must justify: "Does the agent need this for its next decision?"

### Tool Business Logic (`sn_mcp_server/tools/<feature>.py`)

- ✅ Import `SignNowAPIClient`, `tools/models.py`. Pure logic, data transformation.
- ❌ Import Starlette. Import from other `tools/<feature>.py`. Resolve tokens. Module-level mutable state. Generic errors.
- Functions receive `(client: SignNowAPIClient, token: str, ...)` → return curated DTOs.

### Tool Orchestrator (`sn_mcp_server/tools/signnow.py`)

- ✅ Call `_get_token_and_client()`, delegate to `tools/<feature>.py`, use `Annotated[..., Field(...)]` for params.
- ❌ Business logic. Complex conditionals. Data transformation.
- Each tool function: resolve token → call business logic → return result. Docstrings = MCP tool descriptions.

### Auth (`sn_mcp_server/auth.py`, `token_provider.py`)

- ✅ Import `signnow_client`, config.
- ❌ Import from tools layer. Expose tokens/secrets in logs or errors.

### Transport (`sn_mcp_server/app.py`, `cli.py`)

- ✅ Import `server.py`, `config.py`, `auth.py`.
- ❌ Import tools or API client directly. Never touch business logic.

## Coding Standards

- **Language:** English only — code, comments, docstrings, docs.
- **Formatting:** Black, line-length 200. Ruff for linting.
- **Typing:** Strict mypy. No `Any` unless wrapping untyped externals. Use `str | None` over `Optional[str]`. Use `Annotated[..., Field(...)]` for MCP tool parameters.
- **Docstrings:** Required for all public functions/classes. Tool docstrings = MCP descriptions — concise, actionable.
- **Exports:** `__all__` in model files. One logical unit per file.
- **DRY:** Extract to `tools/utils.py` or `signnow_client/utils.py` at 3+ usages. Three similar lines are better than a premature abstraction.

## Critical Gotcha: Transport Leakage

```python
# ✅ Token is a parameter, no transport awareness
def _get_document(client: SignNowAPIClient, token: str, document_id: str) -> DocumentResponse:
    ...

# ❌ Importing Starlette, accessing headers — FORBIDDEN in tools
from starlette.requests import Request
def _get_document(request: Request, document_id: str) -> DocumentResponse:
    token = request.headers["authorization"]
```

## Critical Gotcha: Secrets in Output

```python
# ✅ Masked for diagnostics
from sn_mcp_server.config import _mask_secret_value
logger.info(f"Using token: {_mask_secret_value(token)}")

# ❌ Raw secret — FORBIDDEN
logger.info(f"Using token: {token}")
raise ValueError(f"Auth failed with token {token}")
```

## Bug Fix Protocol

When fixing a documented bug:

1. **Fix the code** in source files.
2. **Verify** lint/type checks pass.
3. **Testability analysis:** Can the fix be verified with unit tests?
   - ✅ **Testable** (logic, transformation, errors, validation): produce a prompt for the Tester agent with bug name, affected files, changes made, and what to assert.
   - ❌ **Not testable** (transport, OAuth2 e2e, external API): state why and request manual verification with `sn-mcp serve` / `sn-mcp http`.

## Verification Checklist

Complete ALL before declaring done:

1. **Static analysis:**
   - `ruff check src/ 2>&1` — must pass
   - `ruff format --check src/ 2>&1` — must pass

2. **Runtime validation** (if business logic or API client changed):
   - Create `scripts/verify-fix.py` → import and call your new function with mock data
   - Execute it. If it crashes, fix and retry.
   - Delete the script when passing.

3. **Regression tests** (if related tests exist):
   - `pytest tests/unit/ -v 2>&1`
   - If fails, fix and retry until green.

Do not ask the user to test. YOU test.

## Rules

- No tests (Tester agent handles them).
- No markdown docs unless explicitly asked.
- No plan references in comments (`@see .plans/`).
- No orphan tools — register in `tools/__init__.py` and document in `README.md`.
- Strictly follow `AGENTS.md`.
