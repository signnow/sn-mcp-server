from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sn-mcp-server")  # имя дистрибутива из pyproject.toml
except PackageNotFoundError:
    __version__ = "0.0.0"

# Экспорт фабрики сервера, чтобы из кода можно было:
#   from sn_mcp_server import create_server
from .cli import create_server, create_http_app, app as cli_app

__all__ = ["__version__", "create_server", "create_http_app", "cli_app"]