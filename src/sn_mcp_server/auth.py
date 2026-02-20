import base64
import secrets
import time
from urllib.parse import urlencode, urlparse
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.status import HTTP_201_CREATED

from signnow_client import SignNowAPIClient
from signnow_client.config import load_signnow_config

from .config import load_settings
from .token_provider import TokenProvider

# ============= CONFIG =============
settings = load_settings()
signnow_config = load_signnow_config()

# ============= KEYGEN (RS256) =============
private_key = settings.get_rsa_private_key()

public_key = private_key.public_key()
public_pem = public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)

# JWKS
numbers: _rsa.RSAPublicNumbers = public_key.public_numbers()
e_b = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
n_b = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _url(base: str | Any, *parts: str) -> str:
    """Join base URL with path parts, normalizing slashes."""
    base = str(base).rstrip("/")
    path = "/".join(p.strip("/") for p in parts if p)
    return f"{base}/{path}" if path else base


JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "use": "sig",
            "kid": settings.oauth_jwk_kid,
            "alg": "RS256",
            "n": b64url(n_b),
            "e": b64url(e_b),
        }
    ]
}

# ============= Helpers =============

# Initialize SignNow API client
signnow_client = SignNowAPIClient(signnow_config)


def _verify_jwt(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=[settings.effective_resource_http_url, settings.effective_resource_sse_url],  # both resources are considered valid audiences
            issuer=str(settings.oauth_issuer),
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        return None


def _token_response(signnow_response: dict[str, Any]) -> JSONResponse:
    """Build OAuth token response from SignNow API response."""
    return JSONResponse(
        {
            "token_type": signnow_response.get("token_type", "Bearer"),
            "access_token": signnow_response.get("access_token"),
            "expires_in": signnow_response.get("expires_in", settings.access_ttl),
            "refresh_token": signnow_response.get("refresh_token"),
            "scope": signnow_response.get("scope", "offline_access *"),
        }
    )


def _require_string(value: Any, param: str) -> tuple[str | None, JSONResponse | None]:
    """Validate form param is non-empty string. Returns (value, error_response)."""
    if not value:
        return None, JSONResponse({"error": "invalid_request", "error_description": f"{param} required"}, status_code=400)
    if not isinstance(value, str):
        return None, JSONResponse({"error": "invalid_request", "error_description": f"{param} must be a string"}, status_code=400)
    return value, None


# ============= OAuth endpoints =============
def _openid_configuration() -> dict[str, Any]:
    """Build OAuth/OIDC discovery document with correct URLs."""
    base = str(settings.oauth_issuer).rstrip("/")
    return {
        "issuer": str(settings.oauth_issuer),
        "authorization_endpoint": _url(base, "authorize"),
        "token_endpoint": _url(base, "oauth2/token"),
        "jwks_uri": _url(base, ".well-known/jwks.json"),
        "registration_endpoint": _url(base, "oauth2/register"),
        "scopes_supported": ["offline_access", "*"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
    }


async def openid_config(_: Request) -> JSONResponse:
    return JSONResponse(_openid_configuration())


async def oauth_as_meta(_: Request) -> JSONResponse:
    return JSONResponse(_openid_configuration())


async def jwks(_: Request) -> JSONResponse:
    return JSONResponse(JWKS)


async def authorize(req: Request) -> RedirectResponse | JSONResponse:
    q = req.query_params
    redirect_uri = q.get("redirect_uri")
    state = q.get("state", "")

    if not redirect_uri:
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri required"}, status_code=400)

    # Validate redirect_uri against allowed list (exact match or same scheme+host; any port when allowed has no port)
    allowed = settings.allowed_redirects_list
    if allowed:
        parsed = urlparse(redirect_uri)
        redirect_scheme = parsed.scheme
        redirect_host = (parsed.hostname or "").lower()
        redirect_port = parsed.port

        def _matches(allowed_uri: str) -> bool:
            if redirect_uri == allowed_uri:
                return True
            a = urlparse(allowed_uri)
            if redirect_scheme != a.scheme:
                return False
            if (a.hostname or "").lower() != redirect_host:
                return False
            # Same scheme and host: allow if exact port match, or if allowed has no port (any port ok)
            if a.port is None:
                return True
            return redirect_port == a.port

        if not any(_matches(a) for a in allowed):
            return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri not allowed"}, status_code=400)

    base_url = _url(signnow_config.app_base, "authorize")
    params: dict[str, str] = {"response_type": "code", "client_id": signnow_config.client_id, "redirect_uri": redirect_uri}
    if state:
        params["state"] = state
    redirect_url = f"{base_url}?{urlencode(params)}"

    return RedirectResponse(redirect_url, status_code=302)


async def token(req: Request) -> JSONResponse:
    form = await req.form()
    grant_type = form.get("grant_type")

    if grant_type == "authorization_code":
        code, err = _require_string(form.get("code"), "code")
        if err:
            return err
        assert code is not None
        signnow_response = signnow_client.get_tokens(code=code)
        if not signnow_response:
            return JSONResponse({"error": "external_token_error"}, status_code=500)
        return _token_response(signnow_response)

    elif grant_type == "refresh_token":
        refresh, err = _require_string(form.get("refresh_token"), "refresh_token")
        if err:
            return err
        assert refresh is not None
        signnow_response = signnow_client.refresh_tokens(refresh_token=refresh)
        if not signnow_response:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return _token_response(signnow_response)

    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


async def introspect(req: Request) -> JSONResponse:
    form = await req.form()
    token = form.get("token", "")
    if isinstance(token, str):
        claims = _verify_jwt(token)
    else:
        claims = None
    active = claims is not None
    resp: dict[str, Any] = {"active": bool(active)}
    if active and claims:
        resp.update(
            {
                "iss": claims["iss"],
                "sub": claims["sub"],
                "aud": claims["aud"],
                "client_id": claims.get("client_id"),
                "scope": claims.get("scope", ""),
                "exp": claims["exp"],
                "iat": claims["iat"],
            }
        )
    return JSONResponse(resp)


async def revoke(req: Request) -> PlainTextResponse | JSONResponse:
    form = await req.form()
    token, err = _require_string(form.get("token"), "token")
    if err:
        return err
    assert token is not None
    try:
        if signnow_client.revoke_token(token):
            return PlainTextResponse("", status_code=200)
        return JSONResponse({"error": "external_revoke_error"}, status_code=500)
    except Exception:
        return JSONResponse({"error": "external_revoke_error"}, status_code=500)


# ============= PRM (Protected Resource Metadata) =============
def prm_for_resource(resource_url: str) -> JSONResponse:
    return JSONResponse(
        {
            "resource": resource_url,
            "authorization_servers": [str(settings.oauth_issuer)],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["offline_access", "*"],
        }
    )


async def prm_root(_: Request) -> JSONResponse:
    return prm_for_resource(settings.effective_resource_http_url)


async def prm_mcp(_: Request) -> JSONResponse:
    return prm_for_resource(settings.effective_resource_http_url)


async def prm_sse(_: Request) -> JSONResponse:
    return prm_for_resource(settings.effective_resource_sse_url)


REGISTERED_CLIENTS: dict[str, dict[str, Any]] = {}


async def register(req: Request) -> JSONResponse:
    data = await req.json()
    redirect_uris = data.get("redirect_uris") or []
    token_method = (data.get("token_endpoint_auth_method") or "none").lower()

    client_id = secrets.token_urlsafe(24)
    client_secret = None
    if token_method == "client_secret_post":
        client_secret = secrets.token_urlsafe(32)

    resp: dict[str, Any] = {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": token_method,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "registration_client_uri": _url(settings.oauth_issuer, "oauth2/register", client_id),
        "client_secret_expires_at": 0,
    }
    if client_secret:
        resp["client_secret"] = client_secret
        resp["registration_access_token"] = secrets.token_urlsafe(24)

    return JSONResponse(resp, status_code=HTTP_201_CREATED)


# ============= Middleware =============


class TrailingSlashCompatMiddleware:
    """
    Makes /mcp and /sse equivalent to /mcp/ and /sse/ without redirect.
    """

    def __init__(self, app: Any, accept_exact: tuple[str, ...] = ("/mcp", "/sse")) -> None:
        self.app = app
        self.accept_exact = set(accept_exact)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Rewrite only exact matches to avoid touching sub-routes
            if path in self.accept_exact:
                scope = dict(scope)
                scope["path"] = path + "/"
        await self.app(scope, receive, send)


class BearerJWTASGIMiddleware:
    def __init__(self, app: Any, protect_prefixes: tuple[str, ...] = ("/mcp", "/sse", "/messages")) -> None:
        self.app = app
        self._paths = tuple(protect_prefixes)
        self.token_provider = TokenProvider()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path

        if request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        if any(path.startswith(x) for x in self._paths):
            if not self.token_provider.has_config_credentials():
                token = self.token_provider.get_access_token(dict(request.headers))
                if not token:
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 401,
                            "headers": [
                                (b"www-authenticate", f'Bearer resource_metadata="{_url(settings.oauth_issuer, ".well-known/oauth-protected-resource")}"'.encode()),
                                (b"content-type", b"text/plain; charset=utf-8"),
                            ],
                        }
                    )
                    await send({"type": "http.response.body", "body": b"Unauthorized"})
                    return

        await self.app(scope, receive, send)


# ============= Routes =============
def get_auth_routes() -> list[tuple[str, Any, list[str]]]:
    """Returns all OAuth-related routes"""
    return [
        # OAuth discovery
        ("/.well-known/openid-configuration", openid_config, ["GET", "HEAD", "OPTIONS"]),
        ("/.well-known/oauth-authorization-server", oauth_as_meta, ["GET", "HEAD", "OPTIONS"]),
        ("/.well-known/jwks.json", jwks, ["GET", "HEAD", "OPTIONS"]),
        # OAuth core
        ("/authorize", authorize, ["GET"]),
        ("/oauth2/token", token, ["POST"]),
        ("/oauth2/introspect", introspect, ["POST"]),
        ("/oauth2/revoke", revoke, ["POST"]),
        # PRM (general and per-component)
        ("/.well-known/oauth-protected-resource", prm_root, ["GET", "HEAD", "OPTIONS"]),
        ("/.well-known/oauth-protected-resource/mcp", prm_mcp, ["GET", "HEAD", "OPTIONS"]),
        ("/.well-known/oauth-protected-resource/sse", prm_sse, ["GET", "HEAD", "OPTIONS"]),
        # OAuth registration
        ("/oauth2/register", register, ["POST", "OPTIONS"]),
    ]
