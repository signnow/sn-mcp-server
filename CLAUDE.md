# CLAUDE.md

Project governance, architecture, boundaries, and gotchas live in **[AGENTS.md](./AGENTS.md)** — read it first and follow it for all work in this repo. It is the source of truth; this file only points to it.

Key rule to keep front of mind: **tool contract changes and new tools go through the latest MCP version only** (currently v3.0, in `src/sn_mcp_server/tools/signnow_v3.py`). Never change a released v1.0 or v2.0 tool's input/output contract in place. See the "Tool versioning" boundary in [AGENTS.md](./AGENTS.md).
