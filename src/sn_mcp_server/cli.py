import logging
import sys

import typer
import uvicorn

from .server import create_server

app = typer.Typer(help="SignNow MCP server")

# ============= CLI COMMANDS =============


@app.command()
def serve() -> None:
    """Run MCP server in standalone mode"""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp = create_server()
    mcp.run()


@app.command()
def http(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Run HTTP server with MCP endpoints"""
    uvicorn.run("sn_mcp_server.app:create_http_app", factory=True, host=host, port=port, reload=reload)


# ============= GLOBAL VARIABLES FOR UVICORN =============

if __name__ == "__main__":
    app()
