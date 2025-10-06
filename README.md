<details>
<summary><h1>About SignNow API</h1></summary>

The SignNow REST API empowers users to deliver a seamless eSignature experience for signers, preparers, and senders. Pre-fill documents, create embedded branded workflows for multiple signers, request payments, and track signature status in real-time. Ensure signing is simple, secure, and intuitive on any device.

**What you can do with the SignNow API**:

* Send documents and document groups for signature in a role-based order
* Create reusable templates from documents
* Pre-fill document fields with data
* Collect payments as part of the signing flow
* Embed the document sending, signing, or editing experience into your website, application, or any system of record
* Track signing progress and download the completed documents


</details>

---

# SignNow MCP Server

> A Model Context Protocol (MCP) server that gives AI agents secure, structured access to **SignNow** eSignature workflows — templates, embedded signing, invites, status tracking, and document downloads — over **STDIO** or **Streamable HTTP**.

---

## Table of contents

* [Features](#features)
* [Quick start](#quick-start)

  * [Local (STDIO)](#local-stdio)
  * [Local/Remote (HTTP)](#localremote-http)
  * [Docker](#docker)
  * [Docker Compose](#docker-compose)
* [Configuration](#configuration)

  * [Authentication options](#authentication-options)
  * [SignNow & OAuth settings](#signnow--oauth-settings)
  * [Production key management](#production-key-management)
* [Client setup](#client-setup)

  * [VS Code — GitHub Copilot (Agent Mode)](#vs-code--github-copilot-agent-mode)
  * [Claude Desktop](#claude-desktop)
  * [Cursor](#cursor)
  * [MCP Inspector (testing)](#mcp-inspector-testing)
* [Tools](#tools)
* [FAQ / tips](#faq--tips)
* [Examples](#examples)
* [Useful resources](#useful-resources)

  * [Sample apps](#sample-apps)
  * [API documentation](#api-documentation)
  * [GitHub Copilot extension](#github-copilot-extension)
* [License](#license)

---

## Features

* **Templates & groups**

  * Browse all templates and template groups
  * Create documents or groups from templates (one-shot flows included)
* **Invites & embedded UX**

  * Email invites and ordered recipients
  * **Embedded signing/sending/editor** links for in-app experiences
* **Status & retrieval**

  * Check invite status and step details
  * Download final documents (single or merged)
  * Read normalized document/group structure for programmatic decisions
* **Transports**

  * **STDIO** (best for local clients)
  * **Streamable HTTP** (best for Docker/remote)

---

## Quick start

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
```

#### Option B: Install from Source (Development)

```bash
# 1) Clone & configure
git clone https://github.com/signnow/sn-mcp-server.git
cd sn-mcp-server
cp .env.example .env
# fill in your values in .env

# 2) Install (editable for dev)
pip install -e .

# 3) Run as STDIO MCP server (recommended for local tools & Inspector)
sn-mcp serve
```

> STDIO is ideal for desktop clients and local testing.

### Local/Remote (HTTP)

```bash
# Start HTTP server on 127.0.0.1:8000
sn-mcp http

# Custom host/port
sn-mcp http --host 0.0.0.0 --port 8000

# Dev reload
sn-mcp http --reload
```

By default, the **Streamable HTTP** MCP endpoint is served under `/mcp`. Example URL:

```
http://localhost:8000/mcp
```

### Docker

```bash
# Build
docker build -t sn-mcp-server .

# Run HTTP mode (recommended for containers)
docker run --env-file .env -p 8000:8000 sn-mcp-server sn-mcp http --host 0.0.0.0 --port 8000
```

> STDIO inside containers is unreliable with many clients. Prefer HTTP when using Docker.

### Docker Compose

```bash
# Only the MCP server
docker-compose up sn-mcp-server

# Both services (if defined)
docker-compose up
```

---

## Configuration

Copy `.env.example` → `.env` and fill in values. All settings are validated via **pydantic-settings** at startup.

### Authentication options

**1) Username / Password (recommended for desktop dev flows)**

```
SIGNNOW_USER_EMAIL=<email>
SIGNNOW_PASSWORD=<password>
SIGNNOW_API_BASIC_TOKEN=<base64 basic token>
```

**2) OAuth 2.0 (for hosted/advanced scenarios)**

```
SIGNNOW_CLIENT_ID=<client_id>
SIGNNOW_CLIENT_SECRET=<client_secret>
# + OAuth server & RSA settings below
```

> When running via some desktop clients, only user/password may be supported.

### SignNow & OAuth settings

```
# SignNow endpoints (defaults shown)
SIGNNOW_APP_BASE=https://app.signnow.com
SIGNNOW_API_BASE=https://api.signnow.com

# Optional direct API token (not required for normal use)
SIGNNOW_TOKEN=<access_token>

# OAuth server (if you enable OAuth mode)
OAUTH_ISSUER=<your_issuer_url>
ACCESS_TTL=3600
REFRESH_TTL=2592000
ALLOWED_REDIRECTS=<comma,separated,uris>

# RSA keys for OAuth (critical in production)
OAUTH_RSA_PRIVATE_PEM=<PEM content>
OAUTH_JWK_KID=<key id>
```

### Production key management

If `OAUTH_RSA_PRIVATE_PEM` is missing in production, a new RSA key will be generated on each restart, **invalidating all existing tokens**. Always provide a persistent private key via secrets management in prod.

---

## Client setup

### VS Code — GitHub Copilot (Agent Mode)

Create `.vscode/mcp.json` in your workspace:

**STDIO (local):**

```json
{
  "servers": {
    "signnow": {
      "command": "sn-mcp",
      "args": ["serve"],
      "env": {
        "SIGNNOW_USER_EMAIL": "${env:SIGNNOW_USER_EMAIL}",
        "SIGNNOW_PASSWORD": "${env:SIGNNOW_PASSWORD}",
        "SIGNNOW_API_BASIC_TOKEN": "${env:SIGNNOW_API_BASIC_TOKEN}"
      }
    }
  }
}
```

**HTTP (remote or Docker):**

```json
{
  "servers": {
    "signnow": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Then open Chat → **Agent mode**, enable the **signnow** tools, and use them in prompts.

### Claude Desktop

Use Desktop Extensions or the manual MCP config (Developer → Edit config) to add either:

* **STDIO** command: `sn-mcp serve`
* **HTTP** endpoint: `http://localhost:8000/mcp`

Follow Claude’s MCP guide for exact steps and secure secret handling.

### Cursor

Add the server in Cursor’s MCP settings using either **STDIO** (`sn-mcp serve`) or the **HTTP URL** (`http://localhost:8000/mcp`).

### MCP Inspector (testing)

Great for exploring tools & schemas visually.

```bash
# Start Inspector (opens UI on localhost)
npx @modelcontextprotocol/inspector

# Connect (STDIO): run your server locally and attach
sn-mcp serve

# Or connect (HTTP): use http://localhost:8000/mcp
```

You can list tools, call them with JSON args, and inspect responses.

---

## Tools

Each tool is described concisely; use an MCP client (e.g., Inspector) to view exact JSON schemas.

* **`list_all_templates`** — List templates & template groups with simplified metadata.
* **`list_document_groups`** — Browse your document groups and statuses.
* **`create_from_template`** — Make a document or a group from a template/group.
* **`send_invite`** — Email invites (documents or groups), ordered recipients supported.
* **`create_embedded_invite`** — Embedded signing session without email delivery.
* **`create_embedded_sending`** — Embedded “sending/management” experience.
* **`create_embedded_editor`** — Embedded editor link to place/adjust fields.
* **`send_invite_from_template`** — One-shot: create from template and invite.
* **`create_embedded_sending_from_template`** — One-shot: template → embedded sending.
* **`create_embedded_editor_from_template`** — One-shot: template → embedded editor.
* **`create_embedded_invite_from_template`** — One-shot: template → embedded signing.
* **`get_invite_status`** — Current invite status/steps for document or group.
* **`get_document_download_link`** — Direct download link (merged output for groups).
* **`get_document`** — Normalized document/group structure with field values.
* **`update_document_fields`** — Prefill text fields in individual documents.

> Tip: Start with `list_all_templates` → `create_from_template` → `create_embedded_*` / `send_invite`, then `get_invite_status` and `get_document_download_link`.

---

## FAQ / tips

* **STDIO vs Docker?** Prefer **STDIO** for local dev; inside Docker, use **HTTP**.
* **Sandbox vs production?** Start with SignNow’s sandbox/dev credentials; production requires proper OAuth and persistent RSA private key.
* **Where do I see exact tool schemas?** Use **MCP Inspector** or your client’s “tool details” view.
* **Where are examples?** See `examples/` in this repo for starter integrations.

---

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

---

## Useful resources

### Sample apps

Explore ready-to-use sample apps to quickly test preparing, signing, and sending documents from your software using the SignNow API.

Try the [sample apps](https://docs.signnow.com/docs/signnow/sample-apps).

### API documentation
Find technical details on SignNow API requests, parameters, code examples, and possible errors. Learn more about the API functionality in detailed guides and use cases.

Read the [API documentation](https://docs.signnow.com/docs/signnow/welcome).

### GitHub Copilot extension
Develop eSignature integrations directly in GitHub using AI-powered code suggestions. Copilot recommends API calls and code snippets that align with SignNow API guidelines.

Get [SignNow for GitHub Copilot](https://github.com/apps/signnow).

---

## License

MIT — see [LICENSE.md](./LICENSE.md).

---

**About**
SignNow MCP Server — maintained by the SignNow team. Issues and contributions welcome via GitHub pull requests.

---
