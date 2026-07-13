from typing import Any

from fastmcp import FastMCP

from .config import Settings, load_settings
from .tools import register_tools

# Guidance surfaced to the client model in the MCP `initialize` result. SignNow
# document state lives on the server and can change outside the conversation
# (users edit documents in the SignNow editor mid-chat), so the model must not
# reuse state it fetched earlier when performing a write action — it must
# re-fetch the current state first. Both the write actions and the read are
# described by behaviour, not by tool name, so adding a new write tool later
# needs no edit here.
SERVER_INSTRUCTIONS: str = (
    "SignNow entity state — documents, document groups, templates, and template "
    "groups — lives on the server and can change outside this conversation at "
    "any time: users may edit them, add or remove roles, change fields, or "
    "update settings directly in the SignNow editor while you are talking to "
    "them.\n\n"
    "Any entity state you fetched earlier in this conversation (roles, fields, "
    "recipients, status, names) may therefore be stale. Do not trust it when "
    "performing an action that creates, sends, changes, or cancels anything.\n\n"
    "Before any such write action, re-fetch the entity's current state from "
    "SignNow and build the request from that fresh result. If the user says or "
    'implies they just changed something ("I just added a role", "I updated the '
    'field", "I made an edit"), always re-fetch before proceeding, even if you '
    "fetched it moments ago.\n\n"
    "This applies to answering, not only to tool calls: if the user's request "
    "refers to roles, fields, or recipients that do not match what you "
    "remember — for example they ask to send three invites but you recall only "
    "two roles — treat that mismatch as a signal that the state changed. Do not "
    "correct the user or ask what to do from stale memory; re-fetch the current "
    "state first and answer from that."
)


def create_server(cfg: Settings | None = None) -> FastMCP[Any]:
    """Create and configure FastMCP server instance"""
    cfg = cfg or load_settings()

    mcp: FastMCP[Any] = FastMCP("sn-mcp-server", instructions=SERVER_INSTRUCTIONS)
    register_tools(mcp, cfg)
    # load_plugins(mcp, cfg)
    return mcp
