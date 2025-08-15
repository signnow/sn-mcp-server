import json
import time
import logging
import sys
from fastmcp import Context, FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.auth import TokenVerifier
from mcp.server.auth.provider import AccessToken
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse, PlainTextResponse
from starlette.routing import Route, Mount
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import typer
import uvicorn
from .config import Settings, load_settings
from .tools import register_tools
from .auth import (
    get_auth_routes,
    TrailingSlashCompatMiddleware,
    BearerJWTASGIMiddleware
)

app = typer.Typer(help="SignNow MCP server")

# ============= MCP SERVER FUNCTIONS =============

def create_server(cfg: Settings | None = None) -> FastMCP:
    """Create and configure FastMCP server instance"""
    cfg = cfg or load_settings()

    mcp = FastMCP("sn-mcp-server")
    register_tools(mcp, cfg)
    # load_plugins(mcp, cfg)
    return mcp

# ============= HTTP SERVER FUNCTIONS =============

def create_http_app() -> Starlette:
    """Create and configure Starlette HTTP application with MCP endpoints"""
    # ============= CONFIG =============
    settings = load_settings()

    # ============= Build Starlette + MCP mounts =============
    _mcp: FastMCP = create_server()
    
    # Use modern approach instead of deprecated sse_app
    from fastmcp.server.http import create_sse_app
    sse_app = create_sse_app(_mcp, message_path="/", sse_path="/")
    mcp_app = _mcp.http_app(path="/") 

    # Get OAuth routes from auth module
    auth_routes = get_auth_routes()

    # Convert auth route tuples to Route objects
    routes = [
        # OAuth routes
        *[Route(path, handler, methods=methods) for path, handler, methods in auth_routes],
        
        # MCP endpoints
        Mount("/sse", app=sse_app),
        Mount("/mcp", app=mcp_app),
    ]

    app = Starlette(routes=routes, lifespan=mcp_app.lifespan)

    # CORS для браузерных клиентов (инспектор) - ДО BearerJWTMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        allow_credentials=True,
    )

    app.add_middleware(TrailingSlashCompatMiddleware, accept_exact=("/mcp", "/sse"))

    # Bearer middleware после CORS
    app.add_middleware(BearerJWTASGIMiddleware)
    
    return app

# ============= CLI COMMANDS =============

@app.command()
def serve():
    """Run MCP server in standalone mode"""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp = create_server()
    mcp.run()

@app.command()
def http(
    host: str = "0.0.0.0", 
    port: int = 8000,
    reload: bool = False
):
    """Run HTTP server with MCP endpoints"""
    uvicorn.run(
        "sn_mcp_server.cli:http_app", 
        host=host, 
        port=port, 
        reload=reload
    )

# ============= GLOBAL VARIABLES FOR UVICORN =============

# Create HTTP app instance for uvicorn
http_app = create_http_app()

if __name__ == "__main__":
    app() 