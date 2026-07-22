# Contributing

## Development setup

```bash
git clone https://github.com/signnow/sn-mcp-server.git
cd sn-mcp-server

# Create a virtualenv and activate it
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# Install in editable mode with test dependencies
pip install -e ".[test]"

# Copy and fill in your credentials
cp .env.example .env
```

## Running the server locally

```bash
# STDIO — used by Claude Desktop, VS Code Copilot, MCP Inspector
sn-mcp serve

# Streamable HTTP on port 8001 (make target)
make up

# Streamable HTTP — manual
sn-mcp http --host 127.0.0.1 --port 8001
```

## Running tests

### Default suite (unit + integration + api)

```bash
pytest tests/
```

E2E tests are excluded by default (`--ignore=tests/e2e` in `pytest.ini`).

### With coverage

```bash
pytest tests/ --cov --cov-report=term-missing
```

### Specific layers

```bash
pytest tests/unit/           # unit tests only
pytest tests/integration/    # integration tests only
pytest tests/api/            # API client tests only
```

### E2E tests (LLM-based tool selection)

E2E tests require an OpenAI-compatible LLM API. Set these variables in `.env` or your shell:

```bash
LLM_API_HOST=https://your-llm-proxy/v1
LLM_MODEL=gpt-4o-mini
LLM_KEY=sk-...
```

Then run explicitly:

```bash
pytest tests/e2e/ -v
```

When the variables are absent the suite **skips** (exit 0, no failures). E2E tests catch regressions in MCP tool descriptions — they run the real server subprocess against a mock SignNow HTTP server and assert that the LLM picks the correct tool for each natural-language prompt.

### Test layers at a glance

| Layer | Location | What's mocked | Speed |
|---|---|---|---|
| Unit | `tests/unit/` | `SignNowAPIClient` (`MagicMock`) | fast |
| Integration | `tests/integration/` | HTTP layer (`respx`) | fast |
| API | `tests/api/` | HTTP layer (`respx`) | fast |
| E2E | `tests/e2e/` | SignNow HTTP (local mock server) | slow — real LLM calls |

## Code quality

Pre-commit runs `ruff` → `black` → `mypy --strict`. Run them manually before pushing:

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

## Versioning, branching, and tagging

The server follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`). The package version is **derived from git tags** by `hatch-vcs` — there is no version string to edit in `pyproject.toml`. Pushing a `vX.Y.Z` tag triggers `.github/workflows/release-pypi.yml`, which publishes that tag to PyPI (stable PEP 440 releases only).

### How the version number maps to tool versions

Every tool is registered with an explicit `version=` and old contracts are frozen (see the "Tool versioning" boundary in [AGENTS.md](./AGENTS.md)). The MCP server's version tracks those tool versions:

- **`MAJOR` = the highest tool version registered in the server.** When any tool is first promoted to a new highest version `N`, the server jumps to `N.0.0`.
- **`MINOR`** — any later tool reaching the already-current highest major, or any additive, backward-compatible change (a brand-new tool, a new optional field on the latest contract).
- **`PATCH`** — bug fixes and non-contract changes (error-message fixes, docs, internal refactors) that neither add nor alter a tool contract.

**Worked example.** The server is at `v2.10.0` and `upload_document` is at tool-v2. A breaking change to `upload_document` forces a new `upload_document` **v3** contract → because a tool crossed into a new highest version, the server is tagged **`v3.0.0`**. Later, an unrelated tool gets its own v3 contract → the highest major is already 3, so this is a **`v3.1.0`** minor release. This continues until some tool crosses into **v4**, which forces **`v4.0.0`**.

> Note: because a new tool version is added alongside the frozen old one (FastMCP serves the highest by default, but clients can pin an older version), a `MAJOR` bump here signals *"the newest default contract advanced"* rather than a hard break for every client. We still bump `MAJOR` on it, by convention, so the server version always names the highest tool contract it serves.

### Branch model

- **`main` always tracks the latest major version.** All new development targets `main`.
- **Maintenance branches exist only per major version**, named with the bare major: `v2`, `v3`, … They are created on demand — only once `main` has advanced past that major *and* a fix for the older major is actually needed. There is no branch for the major that `main` currently is.

Branch names (`v2`) intentionally differ from tags (`v2.7.1`); they live in separate namespaces. Use `git switch v2` (not `git checkout`) to avoid ref ambiguity.

### Fixing a previous major version

Fixes for an older major are made on that major's maintenance branch and then **merged upward** into every higher major line (up to and including `main`), so no version ever regresses and every supported line gets the fix and its own release tag.

Say `main` is on `v4.x`, and a bug needs fixing in the `v2` line (highest tag `v2.7.1`), with a `v3` line already maintained (highest tag `v3.4.2`):

```bash
# 1. Create the v2 maintenance branch from the latest v2 tag, if it doesn't exist yet.
git switch -c v2 v2.7.1          # skip if branch v2 already exists: git switch v2

# 2. Commit the fix on v2 (directly or via a PR that targets the v2 branch).

# 3. Tag a new PATCH on the v2 line and push branch + tag → releases v2.7.2 to PyPI.
git tag v2.7.2
git push origin v2 v2.7.2

# 4. Merge the fix upward into each higher major line, in order, tagging each.
git switch v3
git merge v2                     # resolve conflicts; keep newer-line code
git tag v3.4.3                   # PATCH bump on the v3 line
git push origin v3 v3.4.3

git switch main                  # main == the v4 line
git merge v3
git tag v4.1.5                   # PATCH bump on the v4 (main) line
git push origin main v4.1.5
```

Each higher line receives a **`PATCH`** bump (it's a bug fix) unless the merge also carries a contract change, in which case bump that line by the rule above.

Rules of thumb:

- Never re-tag or delete a published tag — tags are immutable release inputs.
- Always merge from a lower major into the next-higher one (`v2` → `v3` → `main`); never merge a higher line down into a lower one.
- If a maintenance branch for the target major doesn't exist yet, create it from that major's latest tag before starting the fix.

## Project layout

```
src/
  signnow_client/      # SignNow API client — models, HTTP methods
  sn_mcp_server/       # MCP server — tools, auth, transport
    tools/             # One file per MCP tool
tests/
  unit/
  integration/
  api/
  e2e/                 # LLM-based end-to-end tool selection tests
```

See `ARCHITECTURE.md` for layer rules and dependency direction.
