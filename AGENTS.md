# SignNow MCP Server

Stateless translation layer between AI agents and the SignNow API. Every tool response is curated through `tools/models.py` — never pass raw API JSON. Omit nulls, empty lists, and metadata the agent won't act on.

## Commands

- `make up` installs editable + starts HTTP on port **8001** (NOT 8000). `sn-mcp http` and Docker use 8000.
- Build requires `.git/` directory — `hatch-vcs` reads git tags for version. Without it: version becomes `0.0.0`.
- `pytest` — asyncio-mode=auto, no `@pytest.mark.asyncio` decorators needed. Warnings are suppressed.
- `run_tests.py` has a side effect: runs `pip install -e .[test]` before tests.
- Three test layers: `tests/unit/` (mock `SignNowAPIClient`), `tests/integration/` (mock HTTP layer, test tool→client), `tests/api/` (mock HTTP layer, test client method + request construction). All use `respx` — no real API calls. Both `integration/` and `api/` conftest fixtures use `SignNowConfig.model_construct()` to bypass the credential `@model_validator`. Calling `SignNowConfig()` without any valid credential combination (no `client_id`/`client_secret`, no `basic_token`, no `user_email`/`password`) raises `ValidationError` — `model_construct()` is used in tests to allow a config with all credential fields absent or placeholder.

## Gotchas

- **auth.py module-level side effects.** Importing `auth.py` triggers: config load → RSA keygen (if no PEM) → stdout print of all config → SignNowAPIClient creation. In tests, mock or avoid importing directly.
- **No token caching.** Password grant fires a network call on EVERY tool invocation. Can hit SignNow rate limits under load.
- **RSA key regenerated silently.** If `OAUTH_RSA_PRIVATE_PEM` is missing, `get_rsa_private_key()` generates a new key each restart, invalidating all issued JWTs. No warning logged.
- **`.env` read from CWD.** Both config classes use `env_file=".env"` relative to current working directory, not project root.
- **Empty env vars become defaults silently (string fields only).** String field validators convert `""` to `None` or default values — e.g. `OAUTH_ISSUER=""` silently becomes `http://localhost:8000`. Boolean fields without a custom validator (e.g. `FASTMCP_STATELESS_HTTP`) will raise a Pydantic `ValidationError` on empty string.
- **Dead env vars in `.env.example`.** `SIGNNOW_TOKEN`, `RESOURCE_HTTP_URL`, `RESOURCE_SSE_URL` are not consumed by any config class.
- **Middleware order matters.** Starlette wraps LIFO: actual execution is Bearer → TrailingSlash → CORS → App. Reordering in `app.py` breaks auth.
- **BearerJWT middleware bypassed in password-grant mode.** When config credentials are set, HTTP endpoints have zero token validation.
- **Both `/sse` and `/mcp` mounted.** Legacy SSE transport and modern Streamable HTTP both active. `/sse` uses deprecated FastMCP API.
- **Custom CORS middleware.** `_CORSMiddlewareWithExposeInPreflight` adds `Expose-Headers` to OPTIONS responses — required for Claude MCP client to read `Mcp-Session-Id`.
- **`redirect_target` exclusion.** All request models override `model_dump()` to drop `redirect_target` when `redirect_uri` is absent. SignNow API rejects it otherwise.
- **`signing_link.py` puts access_token in URL query string.** Security concern (browser history, logs, referrer headers).
- **`upload_document` implemented but commented out** in `signnow.py`. Business logic in `document.py` is ready.
- **No CI for tests.** Only release-to-PyPI workflows exist. Tests and linting run locally only.

## Known issues (need fix)

- **Dual formatters.** Both `ruff-format` and `black` run in pre-commit. Can conflict. Pick one.
- **`REGISTERED_CLIENTS` mutable dict in `auth.py`.** Module-level mutable state, violates stateless principle.
- **`cfg` parameter unused.** `register_tools(mcp, cfg)` passes `cfg` to `bind()`, which ignores it.

## Boundaries

### Always

- Curate every API response through `tools/models.py` — never return raw SignNow JSON
- Combine related document/document_group operations into one tool — the tool picks the API path
- Include entity IDs in all error messages — name what failed, why, and which entity
- Unit test every `tools/<feature>.py` function with a mocked `SignNowAPIClient`
- Add integration tests (`tests/integration/`) for every new tool function — one happy path, one error path per tool
- Add API-layer tests (`tests/api/`) for every new `signnow_client` method — assert URL, headers, model type, and each error variant
- Mask secrets with `_mask_secret_value` in any diagnostic output
- **Report progress for every API call in a pagination loop.** Use `ctx.report_progress(progress=loaded, total=api_total, message=f"Loading X")` before each subsequent batch so the client knows work is ongoing, not stalled.
- **Entity type auto-detection order: document_group first, document second.** document_group is the modern entity type; document is legacy. All auto-detection across ALL tools must try `get_document_group_v2` first, fall back to `get_document`. Exceptions must be explicitly justified in code comments.
- **`POST /document/{id}/email2` is the accepted reminder mechanism.** Until SignNow adds a dedicated reminder API, `email2` (send document copy) is the standard way to remind pending signers. When a proper reminder endpoint is available in the SignNow API, migrate `send_invite_reminder` to use it.

### Never

- Import from `sn_mcp_server` inside `signnow_client` — dependency arrow is strictly downward
- Expose tokens, passwords, or PEM content in logs, errors, or tool responses
- Reference Starlette, ASGI, or transport objects in tool functions — use `TokenProvider` for auth
- Add infrastructure-specific code (no AWS/GCP/Azure assumptions)

## Refactoring strategy

Aggressive. When touching code, enforce current standards. Refactor adjacent issues. Don't preserve bad patterns for consistency.

## Reference docs

- `ARCHITECTURE.md` — Authoritative architectural specification: layers, dependency rules, component diagrams, cross-cutting concerns

---

Last updated: 2026-04-03

Maintained by: AI Agents under human supervision
