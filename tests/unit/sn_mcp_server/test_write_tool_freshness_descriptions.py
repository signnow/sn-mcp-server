"""Invariant tests: write-tool descriptions carry a freshness reminder pointing
the model at get_document, while read-only tools stay clean.

Descriptions are captured with the same `recording_tool` monkeypatch pattern used
by test_tool_versions.py. Registrations are keyed by (name, version) because some
tool names (send_invite, create_embedded_invite, get_document) are registered both
as v2.0 in signnow.py and as v1.0 twins in the out-of-scope signnow_v1.py — keying
by name alone would be ambiguous.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import FastMCP

from sn_mcp_server.tools import register_tools

# Freshness keywords any in-scope write-tool clause must surface.
_FRESHNESS_KEYWORDS = ("current", "changed", "editor")

# (name, version) → the freshness clause must be present.
# Only v2.0 tools are modified: version 1.0 is the frozen v1.0.1 compat surface
# (e.g. update_document_fields), which the global server instructions cover
# without touching its description.
_WRITE_TOOLS = [
    ("send_invite", "2.0"),
    ("create_embedded_invite", "2.0"),
    ("cancel_invite", "2.0"),
    ("update_invite_recipient", "2.0"),
]


def _collect_descriptions() -> dict[tuple[str, str], str]:
    """Register all tools and return {(name, version): description}."""
    mcp: Any = FastMCP("freshness-invariant-test")
    descriptions: dict[tuple[str, str], str] = {}
    original_tool = mcp.tool

    def recording_tool(*args: Any, **kwargs: Any) -> Any:
        decorator = original_tool(*args, **kwargs)
        name: str = kwargs.get("name", "")
        version: str = kwargs.get("version", "")
        description: str = kwargs.get("description", "")

        def wrap(fn: Any) -> Any:
            tool_name = name or fn.__name__
            descriptions[(tool_name, version)] = description
            return decorator(fn)

        return wrap

    mcp.tool = recording_tool

    class _StubCfg:
        pass

    register_tools(mcp, _StubCfg())  # type: ignore[arg-type]
    return descriptions


_DESCRIPTIONS = _collect_descriptions()


@pytest.mark.parametrize(("name", "version"), _WRITE_TOOLS)
def test_write_tools_have_freshness_clause(name: str, version: str) -> None:
    """Each in-scope write tool tells the model to re-read the current state.

    Phrased by intent, not by tool name (get_document is intentionally not named
    here; the read tool self-advertises as the fresh-state source).
    """
    assert (name, version) in _DESCRIPTIONS, f"{name!r} v{version} not registered."
    text = _DESCRIPTIONS[(name, version)].lower()
    assert "re-read" in text or "re-fetch" in text, f"{name!r} v{version} description omits a re-read/re-fetch cue."
    assert any(kw in text for kw in _FRESHNESS_KEYWORDS), f"{name!r} v{version} description lacks a freshness keyword {_FRESHNESS_KEYWORDS}."


def test_get_document_description_notes_live_state() -> None:
    """get_document advertises that it returns the current server-side state.

    This is the anchor the abstract 're-read the current state' guidance relies
    on, so its self-description must keep signalling freshness.
    """
    key = ("get_document", "2.0")
    assert key in _DESCRIPTIONS, f"{key} not registered."
    text = _DESCRIPTIONS[key].lower()
    assert "current" in text or "editor" in text


def test_readonly_tool_has_no_freshness_clause() -> None:
    """Guard: read-only list_documents must not carry the write-tool freshness clause.

    Keeps the re-fetch nudge scoped to write actions and avoids provoking
    redundant reads on browse flows (risk §7).
    """
    key = ("list_documents", "1.0")
    assert key in _DESCRIPTIONS, f"{key} not registered."
    text = _DESCRIPTIONS[key].lower()
    assert "may have changed in the signnow editor" not in text
