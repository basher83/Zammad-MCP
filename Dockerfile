# Build stage
FROM python:3.13-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.13-slim AS production

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files and virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml uv.lock ./

# Copy source code
COPY mcp_zammad/ ./mcp_zammad/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Add labels for GitHub Container Registry
LABEL org.opencontainers.image.source="https://github.com/basher83/Zammad-MCP"
LABEL org.opencontainers.image.description="Model Context Protocol server for Zammad ticket system integration"
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD uv run python -c "import mcp_zammad; print('OK')" || exit 1

# MCP doesn't typically expose ports, but keeping for potential future use
EXPOSE 8080

# Run the MCP server
CMD ["uv", "run", "mcp-zammad"]

# Development stage
FROM production AS development

# Run sync as appuser to avoid permission issues
USER appuser
RUN uv sync --frozen

# Enable hot reload for development
ENV PYTHONUNBUFFERED=1
