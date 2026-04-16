from typing import Any

from fastmcp import FastMCP

from .config import Settings, load_settings
from .tools import register_tools


def create_server(cfg: Settings | None = None) -> FastMCP[Any]:
    """Create and configure FastMCP server instance"""
    cfg = cfg or load_settings()

    mcp: FastMCP[Any] = FastMCP(
        "sn-mcp-server",
        instructions=(
            "You are connected to the SignNow MCP server. "
            "BEFORE performing any SignNow action, call signnow_skills(skill_name='signnow101') "
            "to load the required workflow rules. "
            "Critical rule: when the user asks to send a document for signing, "
            "you MUST ask: 'Would you like to preview the document before sending?' "
            "then STOP and return that question as your entire response. "
            "Do NOT answer your own question. Do NOT assume the answer. "
            "Do NOT call any tool in the same turn as the question. "
            "Wait for the human's next message before proceeding."
        ),
    )
    register_tools(mcp, cfg)
    # load_plugins(mcp, cfg)
    return mcp
