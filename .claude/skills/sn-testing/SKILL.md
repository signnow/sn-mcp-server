---
name: sn-testing
description: >
  Testing strategy and conventions for SignNow MCP Server. Use when writing, reviewing,
  or modifying unit tests in this project. Covers per-layer testing patterns, mocking
  conventions (MagicMock for SignNowAPIClient, AsyncMock for Context), async test handling,
  parametrize usage, the analyze protocol (3 YES criteria), and verification steps.
  Do NOT use for implementation, spec writing, or planning.
---

# Testing Standards

## Analyze Protocol

Before writing tests, evaluate each change with the **3 YES criteria** — at least one must be met:

1. **Business Logic:** Does the change affect business logic?
2. **Regression Risk:** Is it prone to regression?
3. **Complexity:** Is it complex enough to benefit from tests?

Do not write useless tests. Quality over quantity.

## Testing Strategy by Layer

### A. Tool Business Logic (`sn_mcp_server/tools/<feature>.py`)

- **Type:** Unit. **Isolation:** Mock `SignNowAPIClient` via `MagicMock`. Mock `fastmcp.Context` via `AsyncMock` when function accepts `ctx`.
- **Focus:** Data transformation, curated response fields, edge cases (empty data, missing optionals), error propagation, status normalization.

```python
class TestFeatureName:
    """Test cases for _feature_function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock SignNowAPIClient."""
        return MagicMock()

    def test_feature_happy_path(self, mock_client):
        """Test successful execution with valid data."""
        mock_client.api_method.return_value = SampleModel(...)

        result = _feature_function(mock_client, "test_token", "param_value")

        assert isinstance(result, ExpectedResponseModel)
        assert result.field == "expected_value"
        mock_client.api_method.assert_called_once_with("test_token", "param_value")
```

### B. Tool Response Models (`sn_mcp_server/tools/models.py`)

- **Type:** Unit. **Focus:** Construction, defaults, `from_*` factories, status normalization, edge cases.

```python
class TestResponseModel:
    """Test cases for ResponseModel."""

    def test_model_construction_with_defaults(self):
        """Test model handles missing optional fields."""
        model = ResponseModel(id="test123", name="Test")
        assert model.optional_field is None

    @pytest.mark.parametrize("raw_status,expected", [
        ("sent", "pending"),
        ("fulfilled", "completed"),
    ])
    def test_status_normalization(self, raw_status, expected):
        """Test raw API status maps to unified status."""
        result = InviteStatusValues.from_raw_status(raw_status)
        assert result == expected
```

### C. API Client Models (`signnow_client/models/`)

- **Type:** Unit. **Focus:** Pydantic validation, serialization (`by_alias=True`), aliases, discriminators, coercion.

```python
class TestApiModel:
    """Test cases for API model validation."""

    def test_model_from_api_payload(self):
        """Test model validates raw API JSON payload."""
        payload = {"field_name": "value", "nested": {"key": "val"}}
        model = ApiModel(**payload)
        assert model.field_name == "value"

    def test_model_serializes_with_alias(self):
        """Test model serializes using API-expected field names."""
        model = RequestModel(from_="sender@example.com")
        dumped = model.model_dump(exclude_none=True, by_alias=True)
        assert "from" in dumped
        assert "from_" not in dumped
```

### D. API Client Methods (`signnow_client/client_*.py`)

- **Type:** Unit. **Isolation:** Dummy subclass overriding `_get`/`_post`/`_put` to capture calls.
- **Focus:** URL construction, header passing, request serialization, response validation.

```python
class _DummyClient(DocumentClientMixin):
    def __init__(self):
        self.last_post = None

    def _post(self, url, headers=None, data=None, json_data=None, validate_model=None):
        self.last_post = {"url": url, "headers": headers, "json_data": json_data}
        if validate_model:
            return validate_model.model_validate({"status": "ok"})
        return None

def test_client_method_passes_correct_url():
    client = _DummyClient()
    client.some_method(token="t", document_id="doc123")
    assert client.last_post["url"] == "/document/doc123/some-endpoint"
```

## Mocking Conventions

| Mock Target | Technique |
|-------------|-----------|
| `SignNowAPIClient` | `MagicMock()` |
| `fastmcp.Context` | `AsyncMock(spec=Context)` |
| API responses | Return real Pydantic model instances (not dicts) |
| API errors | `side_effect` with exception from `signnow_client/exceptions.py` |
| Client internals (for `client_*.py`) | Dummy subclass overriding `_get`/`_post` |

### Rules

- Mock `SignNowAPIClient` methods — never real HTTP calls.
- Return **real Pydantic model instances** from mocks when logic expects validated models.
- Do NOT mock internal Python builtins or Pydantic internals.
- Do NOT mock the function under test — only external dependencies.

## Async Tests

`--asyncio-mode=auto` in `pytest.ini` handles event loop automatically.

```python
async def test_async_function(self, mock_client):
    mock_context = AsyncMock(spec=Context)
    mock_context.report_progress = AsyncMock()

    result = await _async_feature(mock_context, "test_token", mock_client)
    assert result is not None
```

## Output Rules

1. **Location:** `tests/unit/` mirroring source:
   - `src/sn_mcp_server/tools/<feature>.py` → `tests/unit/sn_mcp_server/tools/test_<feature>.py`
   - `src/signnow_client/client_documents.py` → `tests/unit/signnow_client/test_client_documents.py`
2. **Naming:** Files: `test_<module>.py`. Classes: `Test<Feature>`. Methods: `test_<what>_<scenario>`.
3. **Structure:** AAA pattern (Arrange, Act, Assert).
4. **Modern pytest:** `pytest.raises(ExceptionType, match=...)`, `@pytest.mark.parametrize`, fixtures over `setUp`/`tearDown`, raw `assert`.
5. **Docstrings:** One-line for every test class and method. Module docstring: `"""Unit tests for <module> module."""`
6. **No fluff:** Output the test file directly. No explanations of why tests exist.

## Constraints

- ❌ No config changes (`pyproject.toml`, `pytest.ini`, `AGENTS.md`).
- ❌ No network calls — all API mocked.
- ❌ No testing orchestrators (`tools/signnow.py`) — test business logic in `tools/<feature>.py`.
- ✅ Each test independent. No shared mutable state.

## Verification

Complete ALL before declaring done:

1. `pytest tests/unit/ -v 2>&1` — must pass. If fails, fix and retry.
2. `ruff check tests/ 2>&1` — must pass.
3. `ruff format --check tests/ 2>&1` — must pass.

Never declare "Done" until all pass.
