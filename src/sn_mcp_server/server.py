from typing import Any

from fastmcp import FastMCP

from .config import Settings, load_settings
from .tools import register_tools


def create_server(cfg: Settings | None = None, stateless_http: bool = False) -> FastMCP[Any]:
    """Create and configure FastMCP server instance"""
    cfg = cfg or load_settings()

    mcp: FastMCP[Any] = FastMCP("sn-mcp-server", stateless_http=stateless_http)
    register_tools(mcp, cfg)
    # load_plugins(mcp, cfg)
    return mcp
