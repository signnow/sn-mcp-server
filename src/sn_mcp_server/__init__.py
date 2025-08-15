from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sn-mcp-server")  # имя дистрибутива из pyproject.toml
except PackageNotFoundError:
    __version__ = "0.0.0"

# Export server and app factories from their respective modules
from .server import create_server
from .app import create_http_app
from .cli import app as cli_app

__all__ = ["__version__", "create_server", "create_http_app", "cli_app"]