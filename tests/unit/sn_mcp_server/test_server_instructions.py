"""Invariant tests: the MCP server ships non-empty `instructions` that steer the
client model to re-fetch document state before write actions.

The server is stateless and cannot force a re-fetch — these instructions are the
global lever that tells the model not to trust document state cached earlier in
the conversation.
"""

from __future__ import annotations

from typing import cast

from sn_mcp_server.config import Settings
from sn_mcp_server.server import SERVER_INSTRUCTIONS, create_server


class _StubCfg:
    """Truthy stand-in for Settings so create_server() skips load_settings()."""


def _instructions() -> str:
    server = create_server(cast(Settings, _StubCfg()))
    assert server.instructions is not None
    return server.instructions


def test_server_instructions_present() -> None:
    """The server exposes a non-empty instructions string at initialize."""
    instructions = _instructions()
    assert isinstance(instructions, str)
    assert instructions.strip()


def test_create_server_wires_the_constant() -> None:
    """create_server() threads the SERVER_INSTRUCTIONS constant through unchanged."""
    assert _instructions() == SERVER_INSTRUCTIONS


def test_server_instructions_mention_refetch() -> None:
    """Instructions tell the model to re-fetch the current state.

    Phrased by intent, not by tool name: the guidance says to re-fetch/re-read the
    current state and deliberately does NOT hard-code the get_document tool name
    (the read tool advertises itself as the fresh-state source instead).
    """
    text = SERVER_INSTRUCTIONS.lower()
    assert "re-fetch" in text or "re-read" in text
    assert "current" in text
    # Guard the abstraction: no literal tool name leaked back in.
    assert "get_document" not in text


def test_server_instructions_cover_answering_on_conflict() -> None:
    """Re-fetch guidance extends to answering, not just tool calls.

    The reported failure was Claude asserting a stale role count and asking the
    user instead of re-fetching. The instructions must tell the model to treat a
    user/cache mismatch as a re-fetch trigger before answering, not only before a
    write call.
    """
    text = SERVER_INSTRUCTIONS.lower()
    assert "answer" in text
    assert "mismatch" in text or "do not match" in text or "match what you" in text


def test_server_instructions_describe_write_actions() -> None:
    """Write actions are described by behaviour, not a hard-coded tool list.

    Guards the design decision (spec §4.2): adding a new write tool later must not
    require editing this text, so it must talk about creating/sending/changing/
    cancelling rather than enumerating tool names.
    """
    text = SERVER_INSTRUCTIONS.lower()
    assert any(verb in text for verb in ("create", "send", "change", "cancel"))
    # The behavioural phrasing should not have regressed into a tool enumeration.
    assert "send_invite" not in text
    assert "update_document_fields" not in text
