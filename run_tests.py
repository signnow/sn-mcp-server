#!/usr/bin/env python3
"""
Simple test runner script for the sn-mcp-server project.
"""

import subprocess
import sys
from pathlib import Path


def run_tests() -> int:
    """Run the test suite."""
    project_root = Path(__file__).parent

    # Install test dependencies if not already installed
    print("Installing test dependencies...")
    # S603: fixed argv, no shell, executable is sys.executable — controlled input.
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".[test]"], cwd=project_root, check=True)  # noqa: S603

    # Run tests
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], cwd=project_root)  # noqa: S603

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
