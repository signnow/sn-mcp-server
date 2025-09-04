#!/usr/bin/env python3
"""
Simple test runner script for the sn-mcp-server project.
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run the test suite."""
    project_root = Path(__file__).parent

    # Install test dependencies if not already installed
    print("Installing test dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".[test]"], cwd=project_root, check=True)

    # Run tests
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], cwd=project_root)

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
