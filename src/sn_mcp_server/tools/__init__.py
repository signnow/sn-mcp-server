from fastmcp import FastMCP

from sn_mcp_server.config import Settings

from . import signnow, skills


def register_tools(mcp: FastMCP, cfg: Settings) -> None:
    signnow.bind(mcp, cfg)
    skills.bind(mcp, cfg)
