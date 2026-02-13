from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from .server import create_server


def create_http_app() -> Starlette:
    """Create HTTP application with MCP endpoint.

    ``FastMCP.http_app()`` auto-wires:
    * The Streamable-HTTP MCP endpoint at ``/mcp``
    * OAuth discovery, authorize, token, register routes (when auth is set)
    * Bearer-token middleware protecting the MCP endpoint

    We only add CORS on top for browser-based clients (MCP Inspector, etc.).
    """
    mcp = create_server(stateless_http=True)
    app = mcp.http_app(path="/mcp")

    # CORS for browser clients (MCP Inspector, embedded UIs)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        allow_credentials=True,
    )

    return app
