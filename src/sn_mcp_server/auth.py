import os, time, secrets, base64, hashlib, json
from typing import Dict, Set, Tuple, Optional
from starlette.responses import JSONResponse, RedirectResponse, PlainTextResponse
from starlette.requests import Request
from starlette.status import HTTP_201_CREATED
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt
from jwt import PyJWK, PyJWKSet
from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
from .config import load_settings
from signnow_client import SignNowAPIClient
from signnow_client.config import load_signnow_config

# ============= CONFIG =============
settings = load_settings()
signnow_config = load_signnow_config()

# ============= KEYGEN (RS256) =============
private_key = settings.get_rsa_private_key()

public_key = private_key.public_key()
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# JWKS
numbers: _rsa.RSAPublicNumbers = public_key.public_numbers()
e_b = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
n_b = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
def b64url(b: bytes) -> str: return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
JWKS = {
    "keys": [{
        "kty": "RSA",
        "use": "sig",
        "kid": settings.oauth_jwk_kid,
        "alg": "RS256",
        "n": b64url(n_b),
        "e": b64url(e_b),
    }]
}

# ============= Helpers =============

# Initialize SignNow API client
signnow_client = SignNowAPIClient(signnow_config)

def _verify_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=[settings.effective_resource_http_url, settings.effective_resource_sse_url],  # оба ресурса считаем валидными аудиториями
            issuer=str(settings.oauth_issuer),
            options={"require": ["exp", "iat", "iss", "aud"]}
        )
    except Exception:
        return None

# ============= OAuth endpoints =============
async def openid_config(_: Request):
    return JSONResponse({
        "issuer": str(settings.oauth_issuer),
        "authorization_endpoint": f"{str(settings.oauth_issuer)}authorize",
        "token_endpoint": f"{str(settings.oauth_issuer)}oauth2/token",
        "jwks_uri": f"{str(settings.oauth_issuer)}.well-known/jwks.json",
        "registration_endpoint": f"{str(settings.oauth_issuer)}oauth2/register",
        "scopes_supported": ["openid", "profile", "offline_access", "*"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
    })

async def oauth_as_meta(_: Request):
    # можно вернуть тот же объект, что и openid-configuration
    return await openid_config(_)

async def jwks(_: Request):
    return JSONResponse(JWKS)

async def authorize(req: Request):
    q = req.query_params
    redirect_uri = q.get("redirect_uri")
    state = q.get("state", "")

    # Build redirect URL with proper query parameters
    base_url = str(signnow_config.app_base) + "authorize"
    params = {
        "response_type": "code",
        "client_id": signnow_config.client_id,
        "redirect_uri": redirect_uri
    }
    
    # Add state only if it exists
    if state:
        params["state"] = state
    
    # Build query string
    query_string = "&".join(f"{key}={value}" for key, value in params.items())
    redirect_url = f"{base_url}?{query_string}"
    
    return RedirectResponse(redirect_url, status_code=302)

async def token(req: Request):
    form = await req.form()
    grant_type = form.get("grant_type")

    if grant_type == "authorization_code":
        code = form.get("code")

        # Get tokens from SignNow API
        signnow_response = signnow_client.get_tokens(code=code)
        
        if not signnow_response:
            return JSONResponse({"error": "external_token_error"}, status_code=500)
        
        # Return tokens from SignNow API
        return JSONResponse({
            "token_type": signnow_response.get("token_type", "Bearer"),
            "access_token": signnow_response.get("access_token"),
            "expires_in": signnow_response.get("expires_in", settings.access_ttl),
            "refresh_token": signnow_response.get("refresh_token"),
            "scope": "*"
        })

    elif grant_type == "refresh_token":
        refresh = form.get("refresh_token")
        
        if not refresh:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        
        # Get new tokens from SignNow API using refresh token
        signnow_response = signnow_client.refresh_tokens(refresh_token=refresh)
        
        if signnow_response:
            return JSONResponse({
                "token_type": signnow_response.get("token_type", "Bearer"),
                "access_token": signnow_response.get("access_token"),
                "expires_in": signnow_response.get("expires_in", settings.access_ttl),
                "refresh_token": signnow_response.get("refresh_token"),
                "scope": signnow_response.get("scope", "*")
            })
        else:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

async def introspect(req: Request):
    form = await req.form()
    token = form.get("token", "")
    claims = _verify_jwt(token)
    active = claims is not None
    resp = {"active": bool(active)}
    if active:
        resp.update({
            "iss": claims["iss"],
            "sub": claims["sub"],
            "aud": claims["aud"],
            "client_id": claims.get("client_id"),
            "scope": claims.get("scope", ""),
            "exp": claims["exp"],
            "iat": claims["iat"],
        })
    return JSONResponse(resp)

async def revoke(req: Request):
    form = await req.form()
    token = form.get("token")
    
    if not token:
        return JSONResponse({"error": "invalid_request", "error_description": "token parameter required"}, status_code=400)
    
    # Send revoke request to SignNow API
    if signnow_client.revoke_token(token):
        return PlainTextResponse("", status_code=200)
    else:
        return JSONResponse({"error": "external_revoke_error"}, status_code=500)

# ============= PRM (Protected Resource Metadata) =============
def prm_for_resource(resource_url: str):
    return JSONResponse({
        "resource": resource_url,
        "authorization_servers": [str(settings.oauth_issuer)],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["openid", "profile", "offline_access", "*"],
    })

async def prm_root(_: Request):    return prm_for_resource(settings.effective_resource_http_url)
async def prm_mcp(_: Request):     return prm_for_resource(settings.effective_resource_http_url)
async def prm_sse(_: Request):     return prm_for_resource(settings.effective_resource_sse_url)

REGISTERED_CLIENTS: dict[str, dict] = {}

async def register(req: Request):
    data = await req.json()
    redirect_uris = data.get("redirect_uris") or []
    token_method = (data.get("token_endpoint_auth_method") or "none").lower()

    client_id = secrets.token_urlsafe(24)
    client_secret = None
    if token_method == "client_secret_post":
        client_secret = secrets.token_urlsafe(32)

    resp = {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": token_method,
        "grant_types": ["authorization_code","refresh_token"],
        "response_types": ["code"],
        "registration_client_uri": f"{str(settings.oauth_issuer)}/oauth2/register/{client_id}",
        "client_secret_expires_at": 0,
    }
    if client_secret:
        resp["client_secret"] = client_secret
        resp["registration_access_token"] = secrets.token_urlsafe(24)

    return JSONResponse(resp, status_code=HTTP_201_CREATED)

# ============= Middleware =============

class TrailingSlashCompatMiddleware:
    """
    Делает /mcp и /sse эквивалентными /mcp/ и /sse/ без редиректа.
    """
    def __init__(self, app, accept_exact=("/mcp", "/sse")):
        self.app = app
        self.accept_exact = set(accept_exact)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Переписываем только точные совпадения, чтобы не трогать подмаршруты
            if path in self.accept_exact:
                scope = dict(scope)
                scope["path"] = path + "/"
        return await self.app(scope, receive, send)

class BearerJWTASGIMiddleware:
    def __init__(self, app, protect_prefixes=("/mcp", "/sse", "/messages")):
        self.app = app
        self._paths = tuple(protect_prefixes)
        from .token_provider import TokenProvider
        self.token_provider = TokenProvider()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)
        path = request.url.path

        # Пусть CORS снаружи отвечает на preflight
        if request.method == "OPTIONS":
            return await self.app(scope, receive, send)

        if any(path.startswith(x) for x in self._paths):
            if not self.token_provider.has_config_credentials():
                token = self.token_provider.get_access_token(dict(request.headers))
                if not token:
                    await send({
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"www-authenticate",
                             f'Bearer resource_metadata="{str(settings.oauth_issuer)}/.well-known/oauth-protected-resource"'.encode()),
                            (b"content-type", b"text/plain; charset=utf-8"),
                        ],
                    })
                    await send({"type": "http.response.body", "body": b"Unauthorized"})
                    return

        return await self.app(scope, receive, send)

# ============= Routes =============
def get_auth_routes():
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

        # PRM (общий и покомпонентно)
        ("/.well-known/oauth-protected-resource", prm_root, ["GET", "HEAD", "OPTIONS"]),
        ("/.well-known/oauth-protected-resource/mcp", prm_mcp, ["GET", "HEAD", "OPTIONS"]),
        ("/.well-known/oauth-protected-resource/sse", prm_sse, ["GET", "HEAD", "OPTIONS"]),

        # OAuth registration
        ("/oauth2/register", register, ["POST","OPTIONS"]),
    ] 