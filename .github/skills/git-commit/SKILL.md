---
name: git-commit
description: >
  Use when preparing to commit changes or drafting a git commit message in this repo.
---

# Git Commit & Commit Message (SignNow MCP Server)

## Critical rules

* **NEVER commit directly to `main` or `master`.** Always work on a dedicated branch.
* Do not commit unless **all required checks** pass (see below).
* Keep each commit **one logical change** (single change type).
* Commit message follows **Conventional Commits**.

## Workflow

0. **Create (or switch to) a feature branch — MANDATORY**

* NEVER commit to `main` or `master` directly.
* If not already on a feature branch, create one:
  * `git checkout -b <type>/<short-description>` (e.g., `feat/add-embedded-editor`, `fix/token-refresh`)
* Branch naming: `<type>/<short-description>` using the same type vocabulary as commit types.

1. **Check what changed**

* `git status -sb`
* If changes are mixed, split into separate commits using `git add -p`.

2. **Review staged diff**

* Stage what belongs to this commit.
* Inspect: `git diff --cached`

3. **Run required checks (must be green)**

```bash
pytest tests/unit/ -v
ruff check src/ tests/
ruff format --check src/ tests/
```

* If any command fails, fix the issue and rerun **all** checks.

4. **Compose the commit message**

### Subject format

`<type>(<scope>)?: <subject>`

### Subject rules

* Imperative mood ("Add", "Fix", "Remove", "Prevent", ...)
* No trailing period
* Prefer **≤ 72 chars**

### Body (optional)

* Explain **why**, not just what.
* Wrap lines at ~80 chars.

### Breaking changes (if applicable)

* Add `!` after type/scope: `feat!: ...` or `feat(tools)!: ...`
* Add footer:

  * `BREAKING CHANGE: <what breaks and migration notes>`

5. **Commit**

* One-liner (no body/footer needed):

  * `git commit -m "..."`
* Otherwise:

  * `git commit` and write subject + body in editor.

6. **Post-commit sanity**

* `git show --stat`
* Ensure no accidental files were committed.

7. **Push**

* `git push`

8. **Create Pull Request (if none exists)**

* After pushing, check whether a PR already exists for the current branch:
  * Use the GitHub MCP tool (`search_pull_requests`) to check.
* If **no PR exists** → create one immediately.

### PR title format

`<title>` must be a short imperative summary of the **whole task** (not just the last commit). To understand what the task is about, read the corresponding plan file in `.plans/` (e.g., `.plans/Plan-{TASK_NAME}.md`).

Examples:
* `Add embedded editor tool`
* `Fix token refresh loop on expired OAuth2 JWT`

### PR body

Fill in:
* **Summary** — one-paragraph description of what was changed and why
* **Changes** — bullet list of what was added/changed/removed
* **Tests** — note whether tests were added or why they were not needed

9. **PR alignment**

* Branch name: short descriptive name matching the task (e.g., `add-embedded-editor`, `fix-token-refresh`).
* PR title must be **exactly the same** as the intended final commit message (squash title).

## Type selection

* `feat` — new capability/behavior
* `fix` — bug fix
* `refactor` — no behavior change
* `docs` — docs only
* `test` — tests only
* `chore` — tooling/CI/deps/maintenance

## Scope suggestions (optional)

Use a stable domain/component name: `tools`, `client`, `auth`, `models`, `cli`, `config`, `tests`, `ci`, `docker`.

## Examples

* `feat(tools): Add update_document_fields tool`
* `fix(auth): Prevent token refresh loop on expired OAuth2 JWT`
* `refactor(client): Simplify document group mixin error handling`
* `test(tools): Add invite_status business logic coverage`
* `docs: Update README tools section`
* `chore: Update ruff lint config`
