# Plan: SN-30630 — Skills Directory & `signnow_skills` MCP Tool

**Spec:** `.specs/Spec-SN-30630-Skills-Tool.md`
**Affected layers:** Tool Response Models, Tool Business Logic, Tool Registration, Tests, Documentation
**No `signnow_client` changes. No `signnow.py` changes.**

---

## Philosophy Checklist (pre-flight)

- [x] Every response model carries ONLY minimum data? — `SkillSummary` has 2 fields; `SkillResponse` carries only what is active for the mode.
- [x] Tool count minimized? — One new tool (`signnow_skills`) handles both list and fetch via a single optional parameter.
- [x] Every business logic function testable with mocked client? — No client involved; pure filesystem logic tested via `tmp_path`.
- [x] All error messages specific — operation, entity ID, cause? — Both `ValueError`s name entity and list available options.
- [x] Zero state, zero caching, zero infrastructure coupling? — `_SKILLS_DIR` is an immutable `Path` constant, not mutable state; each call re-scans.
- [x] Feature actually needed now? — Required by SN-30630 acceptance criteria.
- [x] `signnow_client/` has zero imports from `sn_mcp_server/`? — No `signnow_client` changes in this task.

---

## Phase 1: Skills Content

> Foundational — no code dependencies. Must exist before tests or business logic can reference real files.

- [ ] **[Content]** Create directory `src/sn_mcp_server/skills/`.

- [ ] **[Content]** Create `src/sn_mcp_server/skills/signnow101.md` with the following structure:

  **Front-matter** (exactly two `---` delimiters, single-line values):
  ```
  ---
  name: signnow101
  description: SignNow concepts reference: entity types, post-upload actions, invite types, and tool-to-API endpoint mappings.
  ---
  ```

  **Body sections** (all four required by Appendix A of the spec):

  1. **Entity Types Glossary** — Markdown table with four rows: Document, Template, Document Group, Template Group. Each row describes what the entity is, how it is created, and its relationship to signing workflows.

  2. **Post-Upload Action Table** — Markdown table mapping user goals (sign myself, send freeform, send role-based, create template, check status, download) to the exact MCP tool name and a one-line note.

  3. **Invite Types Reference** — Markdown table: Freeform, Role-Based, Embedded Invite, Field Invite. Columns: how fields are placed, who configures them, which tool to call.

  4. **Tool → API Endpoint Mapping Table** — Markdown table with three columns: MCP Tool name, HTTP Method, SignNow API Endpoint path. Must include every tool registered in the server as of this task (13 rows including `signnow_skills` itself marked as local/no API call). Tool names must exactly match the registered MCP tool names — this table is the staleness guard source of truth.

  > **Constraint:** Keep total file size under 5,000 words (per spec §7 risk mitigation). Single-line `description` in front-matter only — no multi-line values.

---

## Phase 2: Tool Response Models

> Layer 3 — `sn_mcp_server/tools/models.py`. Imports: `pydantic` only (plus Layer 1 type refs already present).

- [ ] **[Tool Model]** In `src/sn_mcp_server/tools/models.py`, append two Pydantic models after the existing model definitions (at the end of the file, before any `__all__` if present):

  **`SkillSummary(BaseModel)`**
  - Field `name: str` — skill identifier (filename stem from `Path.stem`). Field description: `"Skill identifier (filename without .md extension)"`.
  - Field `description: str` — one-line description from front-matter. Field description: `"One-line description from skill front-matter"`.
  - No optional fields — both are always present (graceful degradation fills empty string for `description`).

  **`SkillResponse(BaseModel)`**
  - Field `skills: list[SkillSummary] | None = Field(default=None, ...)` — populated in list mode only.
  - Field `name: str | None = Field(default=None, ...)` — populated in fetch mode only.
  - Field `body: str | None = Field(default=None, ...)` — populated in fetch mode only; front-matter stripped.
  - Docstring must state the two mutually exclusive modes clearly (as in spec §4.1).

  > **Constraint:** No raw API fields. No `model_config`. No validators needed — these are output-only DTOs.

---

## Phase 3: Tool Business Logic

> Layer 4 — new file `src/sn_mcp_server/tools/skills.py`. Imports: `pathlib.Path`, `re`, `typing.Annotated`, `typing.Any`, `fastmcp.FastMCP`, `mcp.types.ToolAnnotations`, `pydantic.Field`, and `.models.SkillResponse`, `.models.SkillSummary`. No `SignNowAPIClient`. No `TokenProvider`. No Starlette.

- [ ] **[Tool Logic]** Create `src/sn_mcp_server/tools/skills.py`.

  **Module-level constant:**
  ```
  _SKILLS_DIR: Path = Path(__file__).parent.parent / "skills"
  ```
  This is an immutable path constant resolved once at import time. It is NOT mutable state (it never changes after module load). Add a comment explaining this distinction per the spec note.

- [ ] **[Tool Logic]** Implement `_parse_frontmatter(content: str) -> tuple[dict[str, str], str]`:

  Logic (prose):
  1. If `content` does not start with `"---\n"` → return `({}, content)` immediately.
  2. Search for a second `"---\n"` occurrence after the opening delimiter (start search at index 4).
  3. If not found → return `({}, content)` — treat unclosed front-matter as absent.
  4. Extract the YAML block text between offset 4 and the start of the closing delimiter.
  5. Parse the block using `re.findall(r'^(\w+)\s*:\s*(.+)$', yaml_block, re.MULTILINE)` — produces a list of `(key, value)` tuples.
  6. Strip each value string (`.strip()`).
  7. Return `(dict(matches), content_after_closing_delimiter)` where `content_after_closing_delimiter` begins immediately after the `"---\n"` closing delimiter.

  > No PyYAML. No additional dependencies.

- [ ] **[Tool Logic]** Implement `_list_skills(skills_dir: Path) -> SkillResponse`:

  Logic (prose):
  1. If `not skills_dir.exists()` → raise `ValueError(f"Skills directory not found: {skills_dir}")`.
  2. Collect files: `sorted(skills_dir.glob("*.md"))`.
  3. For each `file` in the sorted list:
     a. Read text with `file.read_text(encoding="utf-8")`.
     b. Call `_parse_frontmatter(content)` → `(fm, _)`.
     c. Build `SkillSummary(name=fm.get("name", file.stem), description=fm.get("description", ""))`.
  4. Return `SkillResponse(skills=[...summaries...], name=None, body=None)`.

- [ ] **[Tool Logic]** Implement `_get_skill(skills_dir: Path, skill_name: str) -> SkillResponse`:

  Logic (prose):
  1. Build `target = skills_dir / f"{skill_name}.md"`.
  2. If `not target.exists()`:
     a. Collect available: `[f.stem for f in sorted(skills_dir.glob("*.md"))]`.
     b. Format available string: `", ".join(available)` if `available` else `"(none)"`.
     c. Raise `ValueError(f"Skill '{skill_name}' not found. Available skills: {available_str}")`.
  3. Read `target.read_text(encoding="utf-8")` → `content`.
  4. Call `_parse_frontmatter(content)` → `(fm, body)`.
  5. Return `SkillResponse(skills=None, name=fm.get("name", skill_name), body=body.strip())`.

- [ ] **[Tool Logic]** Implement `bind(mcp: FastMCP, cfg: Any) -> None`:

  Inside `bind`, define and register the async tool function:

  **`async def signnow_skills(skill_name: Annotated[str | None, Field(...)] = None) -> SkillResponse`**

  Decorator: `@mcp.tool(name="signnow_skills", description="...", annotations=ToolAnnotations(...), tags=["skill", "reference"])`. Use exact values from spec §4.2.

  Tool function body logic (prose):
  1. If `skill_name is None` → return `_list_skills(_SKILLS_DIR)`.
  2. Else → return `_get_skill(_SKILLS_DIR, skill_name)`.
  3. Any `ValueError` from the called functions propagates naturally as an MCP tool error — no try/except needed.

  > `cfg` parameter is accepted for interface consistency but unused. Add `# cfg unused — no auth` comment.
  > The tool captures `_SKILLS_DIR` from the module level only — no closure over token/client.

---

## Phase 4: Tool Registration

> Layer 5 — `src/sn_mcp_server/tools/__init__.py`. Thin wiring only.

- [ ] **[Registration]** Modify `src/sn_mcp_server/tools/__init__.py`:
  1. Add import: `from . import skills` (alongside existing `from . import signnow`).
  2. Inside `register_tools(mcp, cfg)`, add the call: `skills.bind(mcp, cfg)` after `signnow.bind(mcp, cfg)`.

  > Do NOT modify `signnow.py`. This is the designated registration pattern for tools with no auth dependency (spec §2 note).

---

## Phase 5: Tests

> All tests live in `tests/unit/sn_mcp_server/tools/test_skills.py`. Use `tmp_path` pytest fixture. No `MagicMock` for `SignNowAPIClient` — this module has no client dependency.

- [ ] **[Tests]** Create `tests/unit/sn_mcp_server/tools/test_skills.py`.

  Import: `from pathlib import Path`, `import pytest`, `from sn_mcp_server.tools.skills import _list_skills, _get_skill, _parse_frontmatter`, `from sn_mcp_server.tools.models import SkillResponse, SkillSummary`.

  Organize into test classes by function under test.

---

### `TestParseFrontmatter`

- [ ] **[Tests]** `test_parse_frontmatter_valid` — call `_parse_frontmatter("---\nname: foo\ndescription: bar\n---\nbody")`. Assert return value equals `({"name": "foo", "description": "bar"}, "body")`.

- [ ] **[Tests]** `test_parse_frontmatter_no_delimiters` — call `_parse_frontmatter("just body")`. Assert return value equals `({}, "just body")`.

- [ ] **[Tests]** `test_parse_frontmatter_unclosed` — call `_parse_frontmatter("---\nname: foo\n")` (no closing `---`). Assert return value equals `({}, "---\nname: foo\n")`.

---

### `TestListSkills`

- [ ] **[Tests]** `test_list_skills_returns_all` — write two `.md` files (`alpha.md`, `beta.md`) each with valid `name` and `description` front-matter into `tmp_path`. Call `_list_skills(tmp_path)`. Assert result is a `SkillResponse` with `skills` list of length 2, `name=None`, `body=None`. Assert each `SkillSummary` carries the correct `name` and `description` from front-matter.

- [ ] **[Tests]** `test_list_skills_sorted_alphabetically` — write `z_skill.md` then `a_skill.md` into `tmp_path` (creation order reversed). Call `_list_skills(tmp_path)`. Assert `skills[0].name == "a_skill"` and `skills[1].name == "z_skill"`.

- [ ] **[Tests]** `test_list_skills_empty_dir` — create `tmp_path` with no `.md` files (it exists but is empty). Call `_list_skills(tmp_path)`. Assert result is `SkillResponse(skills=[], name=None, body=None)`.

- [ ] **[Tests]** `test_list_skills_missing_dir` — pass a path that does not exist: `tmp_path / "nonexistent"`. Call `_list_skills(nonexistent_path)`. Assert `ValueError` is raised and the message contains `"Skills directory not found"`.

- [ ] **[Tests]** `test_list_skills_degraded_frontmatter` — write `nofm.md` into `tmp_path` with plain body text and no `---` delimiters. Call `_list_skills(tmp_path)`. Assert the resulting `SkillSummary` has `name="nofm"` (from `file.stem`) and `description=""`.

---

### `TestGetSkill`

- [ ] **[Tests]** `test_get_skill_happy_path` — write `signnow101.md` into `tmp_path` with valid front-matter (`name: signnow101`) and body `"# Body\ncontent"`. Call `_get_skill(tmp_path, "signnow101")`. Assert result is `SkillResponse(skills=None, name="signnow101", body="# Body\ncontent")`.

- [ ] **[Tests]** `test_get_skill_body_is_stripped` — write `myskill.md` into `tmp_path` with front-matter and body `"\n\n# Title\n\n"` (leading/trailing whitespace). Call `_get_skill(tmp_path, "myskill")`. Assert `result.body` equals `"# Title"` (stripped).

- [ ] **[Tests]** `test_get_skill_not_found` — write only `signnow101.md` into `tmp_path`. Call `_get_skill(tmp_path, "unknown")`. Assert `ValueError` is raised, message contains `"'unknown' not found"`, and message contains `"signnow101"` in the available list.

- [ ] **[Tests]** `test_get_skill_not_found_empty_dir` — leave `tmp_path` empty (no `.md` files). Call `_get_skill(tmp_path, "anything")`. Assert `ValueError` is raised and message contains `"(none)"`.

---

### `TestStalenessGuard`

- [ ] **[Tests]** `test_signnow101_tool_names_match_registered` — staleness guard test using real files on disk:

  Logic (prose):
  1. Read the real `signnow101.md` from the package `skills/` directory using `Path(__file__)` resolution (navigate up to `src/sn_mcp_server/skills/signnow101.md`).
  2. Extract tool names from the **Tool → API Endpoint Mapping Table** section: find all rows where the first column value starts with a backtick (or parse Markdown table rows) and extract the tool name (strip backticks and whitespace).
  3. Read registered tool names from `signnow.py` and `skills.py` by importing the modules and inspecting registered tools, OR by reading the source files as text and extracting `name="..."` values from `@mcp.tool(` decorator calls using `re.findall`.
  4. Assert that every tool name extracted from the mapping table exists in the set of registered tool names.
  5. If any table entry is missing from registered tools, the assertion error message should list the missing names.

  > This test reads real files — no `tmp_path`. It guards against `signnow101.md` drifting out of sync with the actual registered tools.

---

## Phase 6: Documentation

- [ ] **[Docs]** Update `README.md` — in the tools table (where all MCP tools are listed), add a row for `signnow_skills`:
  - **Tool name:** `signnow_skills`
  - **Parameters:** `skill_name` (optional string) — omit to list skills, provide name to fetch full body.
  - **Description:** "Query the bundled SignNow skill library. Returns all available skills (list mode) or the full Markdown body of a named skill (fetch mode). Use `signnow101` to learn SignNow entity types, invite types, and tool mappings."
  - **Example output (list mode):** `{"skills": [{"name": "signnow101", "description": "..."}]}`
  - **Example output (fetch mode):** `{"name": "signnow101", "body": "# SignNow 101\n..."}`

---

## Phase 7: Verification

- [ ] **[Verification]** Run `pytest tests/unit/sn_mcp_server/tools/test_skills.py -v` — all 13 tests must pass.
- [ ] **[Verification]** Run `pytest` (full suite) — zero regressions.
- [ ] **[Verification]** Run `ruff check src/` — zero violations.
- [ ] **[Verification]** Run `ruff format --check src/` — zero formatting issues.
- [ ] **[Verification]** Manually confirm: `_SKILLS_DIR` resolves to `src/sn_mcp_server/skills/` when the server runs from the project root. Verify by adding a temporary `print(_SKILLS_DIR)` or checking the path in a Python shell — remove before committing.

---

## Dependency Order Summary

```
Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6  →  Phase 7
Content      Models       Logic       Reg.         Tests        Docs         Verify
```

Phases 1 and 2 have no inter-dependency and can be executed in parallel. Phase 3 depends on Phase 2 (imports `SkillSummary`, `SkillResponse`). Phase 4 depends on Phase 3. Phase 5 depends on all prior phases (needs real `signnow101.md` for the staleness guard). Phase 6 is independent of code phases but should be done after the implementation is confirmed working.
