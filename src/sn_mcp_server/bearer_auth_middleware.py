"""Bearer auth middleware that returns 401 with proper headers when token is missing."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from .config import Settings
from .token_provider import TokenProvider


class BearerJWTASGIMiddleware:
    """ASGI middleware that returns 401 with www-authenticate when Bearer token is missing.

    Protects /mcp, /sse, /messages. Skips when config credentials (password grant)
    are set. Lets OPTIONS through for CORS preflight.
    """

    def __init__(
        self,
        app: Any,
        protect_prefixes: tuple[str, ...] = ("/mcp", "/sse", "/messages"),
    ) -> None:
        self.app = app
        self._paths = tuple(protect_prefixes)
        self.token_provider = TokenProvider()
        self.settings = Settings()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path

        if request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if not any(path.startswith(p) for p in self._paths):
            await self.app(scope, receive, send)
            return

        if self.token_provider.has_config_credentials():
            await self.app(scope, receive, send)
            return

        token = self.token_provider.get_token_from_headers(request.headers)
        if not token:
            resource_metadata_url = f"{str(self.settings.oauth_issuer).rstrip('/')}/.well-known/oauth-protected-resource"
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"www-authenticate", f'Bearer resource_metadata="{resource_metadata_url}"'.encode()),
                        (b"content-type", b"text/plain"),
                        (b"content-length", b"12"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return

        await self.app(scope, receive, send)
