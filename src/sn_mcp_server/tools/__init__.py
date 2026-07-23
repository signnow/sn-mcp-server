from fastmcp import FastMCP

from sn_mcp_server.config import Settings

from . import signnow, signnow_v1, signnow_v3, skills


def register_tools(mcp: FastMCP, cfg: Settings) -> None:
    signnow_v1.bind(mcp, cfg)  # v1.0 compat tools — register first
    signnow.bind(mcp, cfg)  # v2.0 tools
    signnow_v3.bind(mcp, cfg)  # v3.0 tools
    skills.bind(mcp, cfg)
