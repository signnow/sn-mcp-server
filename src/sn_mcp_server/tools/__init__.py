from typing import Any

from . import signnow


def register_tools(mcp: Any, cfg: Any) -> None:
    signnow.bind(mcp, cfg)
