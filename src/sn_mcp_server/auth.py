# Authorization is now handled by FastMCP's built-in OAuthProxy.
#
# Previously this module contained:
# - 12 hand-coded OAuth/discovery endpoints
# - BearerJWTASGIMiddleware, TrailingSlashCompatMiddleware
# - RSA key generation, JWKS construction, JWT verification
# - Dynamic client registration
#
# All of the above is provided automatically by FastMCP when an
# ``OAuthProxy`` auth provider is passed to the ``FastMCP`` constructor.
# See config.py:create_auth_provider() for the wiring.
