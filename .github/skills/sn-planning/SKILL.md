---
name: sn-planning
description: >
  Convert technical specifications into step-by-step implementation plans for SignNow MCP
  Server. Use when creating an execution plan, breaking down a spec into tasks, or organizing
  implementation work into phases. Covers phase structure, layer tags, constraint checks, and
  the plan output format. Do NOT use for writing specs, implementing code, or writing tests.
---

# Implementation Planning

## Objective

Convert a Technical Specification into a rigorous, step-by-step Implementation Plan. Define **WHAT** needs to be done, **WHERE** (exact file paths), and in **WHAT ORDER** — so a developer agent can execute each step linearly without ambiguity.

## Output Rules

| Do | Don't |
|----|-------|
| Write function signatures (name, params, return type) | Write function bodies or class implementations |
| Describe logic in prose/pseudo-code | Write actual code blocks |
| Use explicit file paths relative to project root | Leave locations ambiguous |
| Use Markdown checkboxes `- [ ]` for all steps | Use numbered lists without checkboxes |
| Prefix each step with a layer tag | Mix layers within a single step |
| Describe test intent and coverage in prose | Write test code |

## Layer Tags

Prefix every step:

| Tag | Layer | Location |
|-----|-------|----------|
| `[API Model]` | Pydantic API models | `signnow_client/models/` |
| `[API Client]` | HTTP client methods | `signnow_client/client_*.py` |
| `[Tool Model]` | Curated response DTOs | `sn_mcp_server/tools/models.py` |
| `[Tool Logic]` | Business logic | `sn_mcp_server/tools/<feature>.py` |
| `[Tool Orchestrator]` | MCP tool wiring | `sn_mcp_server/tools/signnow.py` |
| `[Registration]` | Tool registration | `sn_mcp_server/tools/__init__.py` |
| `[Config]` | Configuration | `*/config.py` |
| `[Auth]` | Authentication | `sn_mcp_server/auth.py`, `token_provider.py` |
| `[Transport]` | CLI/HTTP app | `sn_mcp_server/cli.py`, `app.py` |
| `[Tests]` | Unit tests | `tests/unit/` |
| `[Docs]` | Documentation | `README.md` |

## Plan Structure

Write to `.plans/Plan-{TASK_NAME}.md`. Group steps into phases following the dependency graph — foundational layers first, dependent layers last.

### Phase 1: API Models
Pure data definitions. Zero dependencies. Represent SignNow API payloads.
- Each step: file path, model purpose, fields.
- **Constraint check:** Models import ONLY from `pydantic`.

### Phase 2: API Client Methods
HTTP communication. Depends only on Phase 1.
- Each step: file path, method signature, brief logic description.
- **Isolation rule:** No `sn_mcp_server.*` imports. Errors via `signnow_client/exceptions.py`.

### Phase 3: Tool Response Models
Token-efficient DTOs for agents. Depends on `pydantic` only.
- Each step: file path, fields included/excluded with reasoning.
- **Constraint check:** Only decision-relevant fields. No raw API passthrough.

### Phase 4: Tool Business Logic
Stateless transformation. Depends on Phase 2 + Phase 3.
- Each step: file path, function signature, numbered pseudo-code.
- **Isolation rule:** Transport-agnostic. No Starlette. No cross-tool imports. Token = parameter.

### Phase 5: Tool Orchestrator & Registration
Thin wiring. Depends on Phase 4.
- Each step: tool function, params, docstring intent, delegation target.
- Registration in `tools/__init__.py` if needed.
- **Constraint check:** Thin wrappers only — resolve token → call logic → return.

### Phase 6: Tests
Unit tests for Phase 4. Mock `SignNowAPIClient`.
- Each step: test file, coverage intent, individual test names + assertions in prose.
- **Constraint check:** No network calls. All mocked. Runnable with `pytest`.

### Phase 7: Documentation & Verification
- Update `README.md` if new tools added.
- Verify docstrings.
- Run `pytest`, `ruff check src/`, `ruff format --check src/`.
- Manual verification instructions.

## Step Granularity

Each step must be **atomic**: "Add model X to file Y", "Add method Z to class W". A developer should complete one step, commit, and move to the next.

## Philosophy Checklist

Before finalizing, verify:

- [ ] Every response model carries ONLY minimum data? (Token Efficiency)
- [ ] Tool count minimized? Could an existing tool handle this? (Tool Minimization)
- [ ] Every business logic function testable with mocked client? (Testability)
- [ ] All error messages specific — operation, entity ID, cause? (Specific Errors)
- [ ] Zero state, zero caching, zero infrastructure coupling? (Stateless)
- [ ] Feature actually needed now? (YAGNI)
- [ ] `signnow_client/` has zero imports from `sn_mcp_server/`? (No Upward Imports)
