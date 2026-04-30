# syntax=docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de469442999ed1a0d7992a5efdf2cffc0e3d769
# Build stage
# Pin to specific digest for reproducibility and security
# python:3.13-slim as of 2025-01-09
FROM python:3.13-slim@sha256:a0779d7c12fc20be6ec6b4ddc901a4fd7657b8a6bc9def9d3fde89ed5efe0a3d AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /uvx /usr/local/bin/

# Copy only dependency files first for better layer caching
# This ensures dependency installation is only re-run when these files change
COPY pyproject.toml uv.lock ./

# Create minimal README.md to satisfy hatchling build requirements
# Using a placeholder prevents cache invalidation when the actual README changes
# The actual README is not needed during the build process
RUN echo "# mcp-zammad\nPlaceholder for build process" > README.md

# Install dependencies with cache mounts for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
  --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev

# Build and install the package
COPY mcp_zammad/ ./mcp_zammad/
RUN --mount=type=cache,target=/root/.cache/pip \
  --mount=type=cache,target=/root/.cache/uv \
  uv pip install --python /app/.venv/bin/python -e .

# Production stage
FROM python:3.13-slim@sha256:a0779d7c12fc20be6ec6b4ddc901a4fd7657b8a6bc9def9d3fde89ed5efe0a3d AS production

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy only the virtual environment from builder (no need for uv in production)
COPY --from=builder /app/.venv /app/.venv

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Copy source code and installed package from builder
COPY --from=builder /app/mcp_zammad /app/mcp_zammad

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Add labels for GitHub Container Registry
LABEL org.opencontainers.image.source="https://github.com/basher83/Zammad-MCP"
LABEL org.opencontainers.image.description="Model Context Protocol server for Zammad ticket system integration"
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"

# IMPORTANT: MCP servers communicate via stdio (stdin/stdout), NOT network ports
# The EXPOSE directive below is ONLY for Docker metadata/documentation
# This server does NOT listen on any network ports - it reads from stdin and writes to stdout
# If you need network access, you would need to wrap the MCP server with an HTTP proxy
# EXPOSE 8080

# Run the MCP server
CMD ["mcp-zammad"]

# Development stage
FROM production AS development

# Switch to root temporarily for installation
USER root

# Install uv for development
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /uvx /usr/local/bin/

# Copy dependency files needed for dev sync
COPY pyproject.toml uv.lock ./

# Create README.md for hatchling build requirements (same as builder stage)
RUN echo "# mcp-zammad\nPlaceholder for build process" > README.md

# Install dev dependencies with cache mounts
RUN --mount=type=cache,target=/root/.cache/pip \
  --mount=type=cache,target=/root/.cache/uv \
  uv sync --dev --frozen && \
  chown -R appuser:appuser /app

# Switch back to appuser
USER appuser

# Enable hot reload for development
ENV PYTHONUNBUFFERED=1