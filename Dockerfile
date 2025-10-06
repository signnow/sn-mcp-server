# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Copy README.md for package metadata
COPY README.md ./

# Copy git directory for version detection
COPY .git/ ./.git/

# Copy source code
COPY src/ ./src/

# Install the package (non-editable) to ensure scripts are created
RUN pip install .

# Set default command to run MCP server
CMD ["sn-mcp", "serve"]

# Expose port for HTTP server (if needed)
EXPOSE 8000 