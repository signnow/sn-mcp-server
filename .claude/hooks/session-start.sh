#!/usr/bin/env bash
# SessionStart hook — makes sure every Claude Code session lands in a
# project where `pytest`, `ruff`, `lint-imports`, and the pre-commit
# hooks all work without manual setup.
#
# Idempotent. Safe to run on every session start — if the venv and
# dev extras are already in place, this is a ~200ms no-op.

set -euo pipefail

cd "$CLAUDE_PROJECT_DIR"

# ----------------------------------------------------------------------
# 1. Python virtualenv. The repo convention is .venv/ at the root.
#    We don't recreate one if it exists — the agent might be reusing
#    an env the human set up manually.
# ----------------------------------------------------------------------
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# ----------------------------------------------------------------------
# 2. Dev extras. pyproject.toml's [dev] extras pull in pre-commit,
#    ruff, mypy, import-linter, diff-cover, and the full [test] set.
#    `-q` keeps startup logs short; the `|| true` keeps us going if the
#    user is offline and everything is already installed.
# ----------------------------------------------------------------------
STAMP=".venv/.dev-deps-stamp"
if [ ! -f "$STAMP" ] || [ pyproject.toml -nt "$STAMP" ]; then
  pip install -q -e ".[dev]" || {
    echo "[session-start] pip install failed — check your network. Continuing."
    exit 0
  }
  touch "$STAMP"
fi

# ----------------------------------------------------------------------
# 3. pre-commit hook install. `default_install_hook_types` in the
#    config means this registers both pre-commit and pre-push.
# ----------------------------------------------------------------------
if [ ! -f .git/hooks/pre-commit ] || [ ! -f .git/hooks/pre-push ]; then
  pre-commit install --install-hooks >/dev/null 2>&1 || true
fi

# ----------------------------------------------------------------------
# 4. .env heads-up. Many tool paths read env vars from the cwd .env;
#    missing it is the #1 reason tools return "no access token" in dev.
# ----------------------------------------------------------------------
if [ ! -f .env ]; then
  echo "[session-start] note: .env is missing. Copy .env.example to .env before running the server."
fi
