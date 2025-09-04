from typing import Any

from fastmcp import FastMCP

from .config import Settings, load_settings
from .tools import register_tools


def create_server(cfg: Settings | None = None) -> FastMCP[Any]:
    """Create and configure FastMCP server instance"""
    cfg = cfg or load_settings()

    mcp: FastMCP[Any] = FastMCP("sn-mcp-server")
    register_tools(mcp, cfg)
    # load_plugins(mcp, cfg)
    return mcp
