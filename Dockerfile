# syntax=docker/dockerfile:1
# Build stage
# Pin to specific digest for reproducibility and security
# python:3.12-slim as of 2025-01-09
FROM python:3.12-slim@sha256:4600f71648e110b005bf7bca92dbb335e549e6b27f2e83fceee5e11b3e1a4d01 AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies with cache mounts for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Production stage
FROM python:3.12-slim@sha256:4600f71648e110b005bf7bca92dbb335e549e6b27f2e83fceee5e11b3e1a4d01 AS production

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files and virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml uv.lock ./

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Copy source code
COPY mcp_zammad/ ./mcp_zammad/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Add labels for GitHub Container Registry
LABEL org.opencontainers.image.source="https://github.com/basher83/Zammad-MCP"
LABEL org.opencontainers.image.description="Model Context Protocol server for Zammad ticket system integration"
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"

# MCP servers communicate via stdio, not HTTP
# Health checks don't apply to stdio-based servers that exit after each request
# Port 8080 is exposed for potential future HTTP API but not currently used
# EXPOSE 8080

# Run the MCP server
CMD ["mcp-zammad"]

# Development stage
FROM production AS development

# Switch to root temporarily for installation
USER root

# Install dev dependencies with cache mounts
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen && \
    chown -R appuser:appuser /app

# Switch back to appuser
USER appuser

# Enable hot reload for development
ENV PYTHONUNBUFFERED=1