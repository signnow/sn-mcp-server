from typing import Any

from . import signnow, skills


def register_tools(mcp: Any, cfg: Any) -> None:
    signnow.bind(mcp, cfg)
    skills.bind(mcp, cfg)
