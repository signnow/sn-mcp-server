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
