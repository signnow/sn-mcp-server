# SignNow MCP Server

A Model Context Protocol (MCP) server that provides SignNow API integration capabilities.

## Quick Start

### Prerequisites

- Python 3.11+ installed on your system
- Environment variables configured

### 1. Setup Environment Variables

```bash
# Create .env file with your SignNow credentials
# You can copy from env.example if you have the source code
# Or create .env file manually with required variables (see Environment Variables section below)
```

### 2. Install and Run

#### Option A: Install from PyPI (Recommended)

```bash
# Install the package from PyPI
pip install signnow-mcp-server

# Run MCP server in standalone mode
sn-mcp serve

# Run HTTP server with MCP endpoints
sn-mcp http

# Run HTTP server on custom host/port
sn-mcp http --host 127.0.0.1 --port 8080

# Run HTTP server with auto-reload (for development)
sn-mcp http --reload
```

#### Option B: Install from Source (Development)

```bash
# Install the package in development mode
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

# Run HTTP server (recommended for Docker)
docker run --env-file .env -p 8000:8000 sn-mcp-server sn-mcp http --host 0.0.0.0 --port 8000

docker run --env-file .env -p 8000:8000 sn-mcp-server sn-mcp http

# Run MCP server in STDIO mode (NOT recommended for Docker)
# Note: STDIO mode in Docker containers may not work properly with MCP clients
# Use local installation instead: sn-mcp serve
docker run -i --env-file .env sn-mcp-server sn-mcp serve
```

**Important**: For MCP Inspector and other MCP clients, use local installation (`sn-mcp serve`) instead of Docker for STDIO mode. Docker is better suited for HTTP mode.

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

## Production Deployment

**Important**: When deploying to production, you **MUST** set the `OAUTH_RSA_PRIVATE_PEM` environment variable with a persistent RSA private key. 

If `OAUTH_RSA_PRIVATE_PEM` is not provided, the server will generate a new RSA key on each restart, which will invalidate all previously issued tokens. This can cause authentication issues for existing users.

For production environments:
1. Generate a persistent RSA private key
2. Store it securely (e.g., in a secret management system)
3. Set `OAUTH_RSA_PRIVATE_PEM` environment variable
4. Ensure the key is backed up and can be restored if needed

**Security Note**: Never commit RSA private keys to version control. Always use environment variables or secure secret management systems.

## MCP Tools
<details>
<summary>Tools list</summary>

The server exposes the following tools (brief purpose-oriented descriptions):

### list_all_templates
Lists all templates and template groups across folders with simplified metadata. Use it to choose a starting point for creating documents or groups.

### list_document_groups
Shows your document groups with basic info and statuses. Useful for browsing, monitoring, or selecting a group to manage.

### send_invite
Sends a signing or viewing invite for a document or document group with ordered recipients. Use it to kick off a signing workflow via email.

### create_embedded_invite
Creates an embedded signing session (and links if needed) for a document or group, without email delivery. Ideal for hosting signing inside your app.

### create_embedded_sending
Opens an embedded management/sending experience for a document or group. Use it in-app to configure, edit, or send invites.

### create_embedded_editor
Generates an embedded editor URL to place or adjust fields on a document or group. Great for letting users edit documents within your app.

### create_from_template
Instantiates a document or document group from a template or template group. Typically the first step before inviting or embedding when starting from a template.

### send_invite_from_template
One-shot flow: creates from a template and immediately sends an invite. Fastest way to start signing from a template.

### create_embedded_sending_from_template
One-shot flow: creates from a template and opens embedded sending. Streamlines configuring and sending invites in-app.

### create_embedded_editor_from_template
One-shot flow: creates from a template and returns an embedded editor link. Useful for laying out fields before inviting.

### create_embedded_invite_from_template
One-shot flow: creates from a template and sets up an embedded invite. Perfect for link-based, in-app signing.

### get_invite_status
Retrieves current invite status, including steps and actions, for a document or group. Use it to track progress and drive UI or reminders.

### get_document_download_link
Returns a direct download link for a document; for groups, provides a link to the merged output. Handy for exporting or archiving.

### get_document
Returns a complete, normalized structure of a document or group, including field values (always a unified DocumentGroup). Use it to inspect roles/fields and decide what to prefill or edit.

### update_document_fields
Prefills text fields in one or more individual documents (not groups). Use it to populate values before sending invites.

</details>

## Examples

The `examples/` directory contains working examples of how to integrate the SignNow MCP Server with popular AI agent frameworks:

- **[LangChain](examples/langchain/langchain_example.py)** - Integration with LangChain agents using `langchain-mcp-adapters`
- **[LlamaIndex](examples/llamaindex/llamaindex_example.py)** - Integration with LlamaIndex agents using `llama-index-tools-mcp`
- **[SmolAgents](examples/smolagents/stdio_demo.py)** - Integration with SmolAgents framework using native MCP support

Each example demonstrates how to:
- Start the MCP server as a subprocess
- Convert MCP tools to framework-specific tool formats
- Create agents that can use SignNow functionality
- Handle environment variable configuration

To run an example:
```bash
# Make sure you have the required dependencies installed
pip install langchain-openai langchain-mcp-adapters  # for LangChain example
pip install llama-index-tools-mcp                   # for LlamaIndex example  
pip install smolagents                              # for SmolAgents example

# Set up your .env file with SignNow credentials and LLM configuration
# Then run the example
python examples/langchain/langchain_example.py
python examples/llamaindex/llamaindex_example.py
python examples/smolagents/stdio_demo.py
```

