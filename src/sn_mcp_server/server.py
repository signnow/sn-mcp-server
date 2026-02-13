from typing import Any

from fastmcp import FastMCP

from .config import Settings, create_auth_provider, load_settings
from .tools import register_tools


def create_server(cfg: Settings | None = None, stateless_http: bool = False) -> FastMCP[Any]:
    """Create and configure FastMCP server instance.

    When OAuth credentials are available (and config-based password-grant
    credentials are *not* set), an ``OAuthProxy`` auth provider is attached
    so that HTTP clients can authenticate via the standard MCP OAuth 2.1
    flow with SignNow as the upstream IdP.
    """
    cfg = cfg or load_settings()
    auth = create_auth_provider(cfg)

    mcp: FastMCP[Any] = FastMCP("sn-mcp-server", auth=auth, stateless_http=stateless_http)
    register_tools(mcp, cfg)
    return mcp
