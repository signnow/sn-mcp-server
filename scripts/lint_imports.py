#!/usr/bin/env python
"""Cross-platform import-linter runner.

This checkout shares the `sn_mcp_server` / `signnow_client` import names with the separate
sn-mcp-server-internal project. import-linter builds its graph by importing the configured
root packages from `sys.path`, so without this repo's `src/` taking precedence it can
analyse a globally-installed copy instead. We prepend `src/` here before running it.

Used by the `import-linter` pre-push hook. Replaces the previous
`env PYTHONPATH=src lint-imports` entry, which relied on a POSIX `env` binary and so failed
for contributors on native Windows shells (no coreutils / git-bash). Running import-linter
in-process from Python is portable across Linux, macOS, and Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

from importlinter.cli import lint_imports

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
_CONFIG = _REPO_ROOT / "pyproject.toml"


def main() -> int:
    """Run import-linter with this repo's src/ taking precedence on sys.path."""
    sys.path.insert(0, str(_SRC))
    return lint_imports(config_filename=str(_CONFIG))


if __name__ == "__main__":
    raise SystemExit(main())
