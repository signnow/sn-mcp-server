---
name: sn-spec-writing
description: >
  Write technical specifications for SignNow MCP Server features. Use when designing
  a new feature, writing a spec, performing architecture review, or converting a feature
  idea into requirements. Covers the analysis protocol (philosophy check, layer check,
  tool design, auth, errors, testability), spec output format, and Pydantic model design.
  Do NOT use for implementation, testing, or planning — those have dedicated skills.
---

# Technical Specification Writing

## Analysis Protocol

Before designing any feature, run every check in order. If any check fails, reject or redesign before proceeding.

### 1. Philosophy Check

| Principle | Question |
|-----------|----------|
| Thin Translator | Does this maintain the stateless translation identity? If it adds state, caching, or agent-side logic — redesign. |
| Simplicity | Is this the simplest possible solution? Can it have fewer moving parts? |
| YAGNI | Is the feature actually needed now, or is it speculative? |

### 2. Architecture & Layer Check

- Which layers are affected? Consult the layer access matrix (skill: `sn-architecture`).
- Upward imports (`signnow_client/` → `sn_mcp_server/`)? → **Reject.**
- Tool functions importing Starlette or referencing HTTP headers? → **Redesign** to use `TokenProvider`.
- Module-level mutable state, global caches, singletons? → **Reject.**

### 3. Tool Design Check

- Does this need a **new** MCP tool? Can the functionality join an existing tool instead?
- If new: does it overlap with existing tools? Could one tool handle both with an internal branch?
- Are parameters minimal and clear? Can an agent use this from the docstring alone?
- Does the response model include **only** decision-relevant fields? No raw API passthrough.

### 4. Auth & Transport Check

- Works across all 3 auth strategies (password grant, bearer header, OAuth2 JWT)?
- Works across all 3 transports (STDIO, Streamable HTTP, SSE)?
- No deployment-environment assumptions?

### 5. Error Handling Check

- List every failure mode explicitly.
- Each failure mode: specific error message with operation name, entity ID, cause.
- SignNow API errors translated via `signnow_client/exceptions.py`.
- Pydantic validation errors surfaced as clear parameter-level messages before any API call.

### 6. Testability Check

- Business logic testable by injecting a mocked `SignNowAPIClient`?
- List test cases: happy path + each failure mode.
- Any tests require network calls? → **Redesign.**
- New tests mirror `tests/unit/` source structure.

### 7. Documentation Check

- `README.md` needs updating? (New tools, auth changes, transport changes.)
- Tool docstrings concise, accurate, actionable for an AI agent?
- Tool registered in `tools/__init__.py` → `register_tools()`?

## Output Style Rules

| Do | Don't |
|----|-------|
| Define Pydantic models as complete runnable Python (models ARE the spec) | Write function bodies or full implementations |
| Define function signatures with full type hints + docstrings (body = `...`) | Paste raw SignNow API JSON responses |
| Use numbered pseudo-code for business logic flow | Reference Starlette/ASGI/HTTP in tool specs |
| Produce an explicit error catalog table | Skip error scenarios |
| Produce a test matrix table | Write actual test code |

## Spec Output Format

Write to `.specs/Spec-{TASK_NAME}.md` with these sections:

### 1. Business Goal & Value
One paragraph max. Include a Philosophy Check table (Thin Translator, Stateless, Tool Minimization, Token Efficiency, YAGNI, No Infrastructure Coupling — each with ✅/❌ verdict + rationale).

### 2. Affected Layers
Table: Layer | File(s) | Change Type | Description.

### 3. System Diagram (Mermaid)
Sequence diagram: Agent → Tool → Business Logic → API Client → SignNow API → Response Model → Agent.

### 4. Technical Architecture
- **4.1 Pydantic Models** — full Python code for all new/modified models (API-level and response-level).
- **4.2 Function Signatures** — full signatures with type hints, docstrings, body = `...`.
- **4.3 Business Logic Flow** — numbered pseudo-code steps per function.
- **4.4 Error Catalog** — table: Trigger | Exception Class | Message Template.

### 5. Implementation Steps
Ordered checkbox list. Each step = one reviewable unit.

### 6. Test Matrix
Table: Test Name | Input | Mocked API Behavior | Expected Output/Assertion.

### 7. Risk Assessment
Table: Risk | Impact | Likelihood | Mitigation.

### 8. File Structure Summary
Tree view of all new and modified files.
