from fastmcp import FastMCP

from sn_mcp_server.config import Settings

from . import signnow, signnow_v1, skills


def register_tools(mcp: FastMCP, cfg: Settings) -> None:
    signnow_v1.bind(mcp, cfg)  # v1.0 compat tools — register first
    signnow.bind(mcp, cfg)
    skills.bind(mcp, cfg)
