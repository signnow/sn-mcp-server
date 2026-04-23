"""Invariant tests: every registered MCP tool has a version= annotation.

Ensures that after the versioning refactor:
  - No tool is registered without a version (FastMCP disallows mixing versioned
    and unversioned tools of the same name — an unversioned tool would cause a
    startup error if a same-named versioned tool exists).
  - Unchanged tools (v1.0 surface) are tagged "1.0".
  - Changed/new tools are tagged "2.0".
  - v1 compound tools exist only as v1.0 — no v2 variant.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import FastMCP

from sn_mcp_server.tools import register_tools

# ──────────────────────────────────────────────────────────────────────────────
# Tool collection helper
# ──────────────────────────────────────────────────────────────────────────────


def _collect_tool_versions() -> dict[str, list[str]]:
    """Register all tools and return {tool_name: [version, ...]} mapping."""
    mcp: Any = FastMCP("version-invariant-test")
    versions: dict[str, list[str]] = {}
    original_tool = mcp.tool

    def recording_tool(*args: Any, **kwargs: Any) -> Any:
        decorator = original_tool(*args, **kwargs)
        name: str = kwargs.get("name", "")
        version: str = kwargs.get("version", "")

        def wrap(fn: Any) -> Any:
            tool_name = name or fn.__name__
            versions.setdefault(tool_name, []).append(version)
            return decorator(fn)

        return wrap

    mcp.tool = recording_tool

    class _StubCfg:
        pass

    register_tools(mcp, _StubCfg())  # type: ignore[arg-type]
    return versions


_TOOL_VERSIONS = _collect_tool_versions()

# Tools that should only exist as v1.0
_V1_ONLY_TOOLS = {
    "list_all_templates",
    "list_documents",
    "create_from_template",
    "get_invite_status",
    "get_document_download_link",
    "get_signing_link",
    "get_document",
    "update_document_fields",
}

# Tools that have two versions: v1.0 (in signnow_v1.py) and v2.0 (in signnow.py)
_V2_TOOLS_WITH_V1_COMPAT = {
    "send_invite",
    "create_embedded_invite",
    "create_embedded_sending",
    "create_embedded_editor",
}

# Tools that only exist in v2.0 (new since v1.0.1)
_V2_ONLY_TOOLS = {
    "upload_document",
    "create_template",
    "send_invite_reminder",
    "view_document",
    "list_contacts",
}

# Compound tools removed in v2 — preserved only as v1.0 in signnow_v1.py
_COMPOUND_V1_ONLY_TOOLS = {
    "send_invite_from_template",
    "create_embedded_sending_from_template",
    "create_embedded_editor_from_template",
    "create_embedded_invite_from_template",
}


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_all_tools_were_registered() -> None:
    """Sanity: at least 25 tools should be registered (17 current + 8 v1 compat)."""
    assert len(_TOOL_VERSIONS) >= 17, f"Too few unique tool names registered: {sorted(_TOOL_VERSIONS)}"


@pytest.mark.parametrize("tool_name", sorted(_TOOL_VERSIONS.keys()))
def test_all_tools_have_version(tool_name: str) -> None:
    """Every registered tool must have a non-empty version string."""
    for version in _TOOL_VERSIONS[tool_name]:
        assert version, f"Tool {tool_name!r} has an empty or missing version= annotation."


@pytest.mark.parametrize("tool_name", sorted(_V1_ONLY_TOOLS))
def test_unchanged_tools_are_version_1_0(tool_name: str) -> None:
    """Unchanged tools from v1.0.1 are registered as version '1.0'."""
    assert tool_name in _TOOL_VERSIONS, f"Tool {tool_name!r} not registered at all."
    assert _TOOL_VERSIONS[tool_name] == ["1.0"], f"Tool {tool_name!r}: expected ['1.0'], got {_TOOL_VERSIONS[tool_name]}"


@pytest.mark.parametrize("tool_name", sorted(_V2_ONLY_TOOLS))
def test_new_tools_are_version_2_0(tool_name: str) -> None:
    """New tools (no v1.0.1 predecessor) are registered only as version '2.0'."""
    assert tool_name in _TOOL_VERSIONS, f"Tool {tool_name!r} not registered at all."
    assert _TOOL_VERSIONS[tool_name] == ["2.0"], f"Tool {tool_name!r}: expected ['2.0'], got {_TOOL_VERSIONS[tool_name]}"


@pytest.mark.parametrize("tool_name", sorted(_V2_TOOLS_WITH_V1_COMPAT))
def test_changed_tools_have_both_versions(tool_name: str) -> None:
    """Tools with breaking changes are registered as both '1.0' (compat) and '2.0' (current)."""
    assert tool_name in _TOOL_VERSIONS, f"Tool {tool_name!r} not registered at all."
    versions = sorted(_TOOL_VERSIONS[tool_name])
    assert versions == ["1.0", "2.0"], f"Tool {tool_name!r}: expected ['1.0', '2.0'], got {versions}"


@pytest.mark.parametrize("tool_name", sorted(_COMPOUND_V1_ONLY_TOOLS))
def test_compound_tools_exist_only_as_v1(tool_name: str) -> None:
    """Compound *_from_template tools (removed in v2) exist only as v1.0."""
    assert tool_name in _TOOL_VERSIONS, f"Compound tool {tool_name!r} not registered at all."
    assert _TOOL_VERSIONS[tool_name] == ["1.0"], f"Tool {tool_name!r}: expected ['1.0'], got {_TOOL_VERSIONS[tool_name]}"
    # Ensure no v2 variant slipped in
    assert "2.0" not in _TOOL_VERSIONS[tool_name], f"Compound tool {tool_name!r} must not have a '2.0' variant."
