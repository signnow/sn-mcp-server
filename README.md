# SignNow MCP Server

A Model Context Protocol (MCP) server that provides SignNow API integration capabilities.

## Quick Start

### Prerequisites

- Python 3.11+ installed on your system
- Environment variables configured

### 1. Clone and Setup

```bash
git clone <your-repo>
cd sn-mcp-server
cp env.example .env
# Edit .env file with your actual values
```

### 2. Install and Run

```bash
# Install the package
pip install -e .

# Run MCP server in standalone mode
sn-mcp serve

# Run HTTP server with MCP endpoints
sn-mcp http

# Run HTTP server on custom host/port
sn-mcp http --host 127.0.0.1 --port 8080

# Run HTTP server with auto-reload (for development)
sn-mcp http --reload
```

### 3. Using Docker (Alternative)

```bash
# Build the Docker image
docker build -t sn-mcp-server .

# Run MCP server (default)
docker run --env-file .env sn-mcp-server

# Run HTTP server
docker run --env-file .env -p 8000:8000 sn-mcp-server sn-mcp http
```

## Using Docker Compose

### Run sn-mcp-server (MCP Server)

```bash
# Start the MCP server
docker-compose up sn-mcp-server

# Or run in background
docker-compose up -d sn-mcp-server
```

### Run Both Services

```bash
# Start both services
docker-compose up

# Or run in background
docker-compose up -d
```

## Environment Variables

The application uses `pydantic-settings` for configuration management with automatic validation. 
Copy `env.example` to `.env` and configure the following variables:

### Authentication Methods

The SignNow MCP Server supports two authentication methods:

#### 1. Username/Password Authentication (Recommended for MCP Studio)
When running the MCP server through MCP Studio or other MCP clients, use username/password authentication. This method requires the following environment variables:
- `SIGNNOW_USER_EMAIL` - SignNow user email
- `SIGNNOW_PASSWORD` - SignNow user password
- `SIGNNOW_API_BASIC_TOKEN` - SignNow API basic token

#### 2. OAuth Authentication
For advanced use cases, you can use OAuth authentication with the following configuration:
- `SIGNNOW_CLIENT_ID` - SignNow client ID
- `SIGNNOW_CLIENT_SECRET` - SignNow client secret
- OAuth server configuration (see below)

**Note**: When running the MCP server through MCP Studio, only username/password authentication is supported.

### SignNow API Configuration
- `SIGNNOW_APP_BASE` - SignNow app base URL (default: https://app.signnow.com)
- `SIGNNOW_API_BASE` - SignNow API base URL (default: https://api.signnow.com)
- `SIGNNOW_TOKEN` - Your SignNow API token (Optional, for direct API access)

### OAuth Configuration
- `SIGNNOW_CLIENT_ID` - SignNow client ID (required for OAuth)
- `SIGNNOW_CLIENT_SECRET` - SignNow client secret (required for OAuth)

### OAuth Server Configuration
- `OAUTH_ISSUER` - OAuth issuer URL (default: https://lebedev.ngrok.app)
- `ACCESS_TTL` - Access token TTL in seconds (default: 3600)
- `REFRESH_TTL` - Refresh token TTL in seconds (default: 2592000)
- `ALLOWED_REDIRECTS` - Comma-separated list of allowed redirect URIs

### OAuth RSA Key Configuration
- `OAUTH_RSA_PRIVATE_PEM` - RSA private key in PEM format
- `OAUTH_JWK_KID` - JWK key ID

## License

MIT License - see LICENSE file for details.
