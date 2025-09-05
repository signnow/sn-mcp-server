from fastmcp.server.http import create_sse_app
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route

from .auth import (
    BearerJWTASGIMiddleware,
    TrailingSlashCompatMiddleware,
    get_auth_routes,
)
from .config import load_settings


def create_http_app() -> Starlette:
    """Create and configure Starlette HTTP application with MCP endpoints"""
    # ============= CONFIG =============
    settings = load_settings()

    # ============= Build Starlette + MCP mounts =============
    from .server import create_server

    _mcp = create_server()

    # Use modern approach instead of deprecated sse_app
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

    # CORS for browser clients (inspector) - BEFORE BearerJWTMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        allow_credentials=True,
    )

    app.add_middleware(TrailingSlashCompatMiddleware, accept_exact=("/mcp", "/sse"))

    # Bearer middleware after CORS
    app.add_middleware(BearerJWTASGIMiddleware)

    return app
