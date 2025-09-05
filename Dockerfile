# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Copy source code
COPY src/ ./src/

# Install the package using pip to ensure scripts are created
RUN pip install -e .

# Set default command to run MCP server
CMD ["sn-mcp", "serve"]

# Expose port for HTTP server (if needed)
EXPOSE 8000 