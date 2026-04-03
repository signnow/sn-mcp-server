# Tests for sn-mcp-server

This directory contains unit, integration, and API-level tests for the SignNow MCP server.

## Structure

```
tests/
├── unit/                    # Unit tests — mock SignNowAPIClient
│   ├── sn_mcp_server/
│   │   └── tools/
│   └── signnow_client/
├── integration/             # Integration tests — tool → client → HTTP (respx mocked)
│   ├── fixtures/            # JSON response fixtures
│   ├── conftest.py
│   └── test_*.py
├── api/                     # API client tests — client method → HTTP (respx mocked)
│   ├── fixtures/            # JSON response fixtures
│   ├── conftest.py
│   └── test_*.py
└── README.md
```

## Running Tests

### Prerequisites

Install the project with test dependencies:

```bash
pip install -e .[test]
```

### Running All Tests

```bash
# Using pytest directly
pytest tests/ -v

# Using the provided script
python run_tests.py
```

### Running Specific Tests

```bash
# Run only unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/sn_mcp_server/tools/test_list_templates.py -v

# Run specific test method
pytest tests/unit/sn_mcp_server/tools/test_list_templates.py::TestListAllTemplates::test_list_all_templates_success -v
```

## Test Coverage

### Current Tests

- **test_list_templates.py**: Unit tests for the `list_all_templates` function
  - Tests successful template listing with mixed data
  - Tests empty folder scenarios
  - Tests error handling for folder access issues
  - Tests handling of missing optional fields
  - Tests progress reporting functionality

### Test Categories

- **Unit Tests** (`tests/unit/`): Test individual functions in isolation. `SignNowAPIClient` is mocked with `MagicMock()`.
- **Integration Tests** (`tests/integration/`): Test tool functions end-to-end. `respx` intercepts `httpx` — no real API calls. Fixture: `sn_client`, `mock_api`, `token`, `load_fixture`.
- **API Tests** (`tests/api/`): Test `SignNowAPIClient` methods directly. Verifies URL construction, headers, and response parsing. Same respx pattern, fixture: `client`, `mock_api`, `token`, `load_fixture`.

**Key:** Both `integration/` and `api/` use `SignNowConfig.model_construct()` in conftest to bypass the credential `@model_validator`, which enforces that at least one valid credential combination is present. `SignNowConfig(client_id=..., client_secret=...)` with real or fake values validates successfully; `model_construct()` is only needed when tests intentionally supply no credentials at all.

## Writing New Tests

### Unit Test Guidelines

1. **Isolation**: Mock all external dependencies (API clients, database connections, etc.)
2. **Coverage**: Test both success and failure scenarios
3. **Edge Cases**: Test with empty data, missing fields, and error conditions
4. **Naming**: Use descriptive test method names that explain what is being tested

### Example Test Structure

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

class TestMyFunction:
    """Test cases for my_function."""
    
    @pytest.fixture
    def mock_dependency(self):
        """Create a mock dependency."""
        return MagicMock()
    
    @pytest.mark.asyncio
    async def test_my_function_success(self, mock_dependency):
        """Test successful execution."""
        # Setup
        mock_dependency.some_method.return_value = "expected_result"
        
        # Execute
        result = await my_function(mock_dependency)
        
        # Verify
        assert result == "expected_result"
        mock_dependency.some_method.assert_called_once()
```

## Configuration

Test configuration is managed through:

- **pytest.ini**: Main pytest configuration
- **pyproject.toml**: Test dependencies and project configuration

## Dependencies

Test dependencies are defined in `pyproject.toml` under `[project.optional-dependencies]`:

- `pytest>=7.0`: Test framework
- `pytest-asyncio>=0.21`: Async test support
- `pytest-mock>=3.10`: Mocking utilities
- `httpx>=0.25`: HTTP client for integration and API tests
- `respx>=0.22`: HTTP mocking for integration and API tests
