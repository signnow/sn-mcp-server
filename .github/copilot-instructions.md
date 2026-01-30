# Copilot Instructions for AI Coding Agents

## Project Overview
- This project is a Python-based server and client SDK for SignNow API integration, organized under `src/`.
- Major components:
  - `sn_mcp_server/`: Main server logic, CLI, authentication, and tool integrations.
  - `signnow_client/`: Handles SignNow API communication, models, and utility functions.
  - `examples/`: Usage examples for different frameworks (LangChain, LlamaIndex, SmolAgents).
  - `tests/`: Unit tests, organized by module.

## Key Workflows
- **Build & Install:** Use `pip install .` or `python -m build` from the project root.
- **Testing:** Run `pytest` or `python run_tests.py` to execute all tests. Test modules are under `tests/unit/`.
- **Development:** Main code is in `src/`. Use the `Makefile` for common tasks if present.
- **Docker:** Use `docker-compose.yml` and `Dockerfile` for containerized development and deployment.

## Project Conventions
- All source code is under `src/` (not the project root).
- Each tool in `sn_mcp_server/tools/` is a self-contained integration for a specific SignNow feature.
- Models for API payloads are in `signnow_client/models/`.
- Configuration is handled via `config.py` in each main package.
- Use `pyproject.toml` for dependency and build management.

## Integration & Patterns
- The server (`sn_mcp_server/server.py`) loads tools dynamically from `sn_mcp_server/tools/`.
- Authentication logic is in `sn_mcp_server/auth.py` and `sn_mcp_server/token_provider.py`.
- Client logic for SignNow API is abstracted in `signnow_client/client.py` and submodules.
- Example scripts demonstrate integration patterns for external frameworks.

## Examples
- To add a new tool, create a module in `sn_mcp_server/tools/` and register it in `sn_mcp_server/app.py`.
- To extend API models, add to `signnow_client/models/` and update relevant client methods.

## Testing
- Place new tests in `tests/unit/` mirroring the source structure.
- Run all tests with `pytest` or `python run_tests.py`.

## References
- Main entry: `src/sn_mcp_server/app.py`
- Tool pattern: `src/sn_mcp_server/tools/`
- Client pattern: `src/signnow_client/`
- Example usage: `examples/`
- Tests: `tests/unit/`

---
For more details, see `README.md` or source files in the referenced directories.