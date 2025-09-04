from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sn-mcp-server")  # distribution name from pyproject.toml
except PackageNotFoundError:
    __version__ = "0.0.0"

# Export server and app factories from their respective modules
from .app import create_http_app
from .cli import app as cli_app
from .server import create_server

__all__ = ["__version__", "create_server", "create_http_app", "cli_app"]
