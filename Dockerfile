# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
# Build stage
# Pin to specific digest for reproducibility and security
# python:3.13-slim; Renovate updates the digest
FROM python:3.13-slim@sha256:bb2988715db2cf7ace7b53f38f3cffbef7c7046a656bee66245eb0ed386e2e81 AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /uvx /usr/local/bin/

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
FROM python:3.13-slim@sha256:bb2988715db2cf7ace7b53f38f3cffbef7c7046a656bee66245eb0ed386e2e81 AS production

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

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

# The default transport is stdio. Setting MCP_TRANSPORT=http starts the built-in
# HTTP transport on MCP_HOST:MCP_PORT; publish that port only behind trusted
# network controls and inbound client authentication.

# Run the MCP server
CMD ["mcp-zammad"]

# Development stage
FROM production AS development

# Switch to root temporarily for installation
USER root

# Install uv for development
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /uvx /usr/local/bin/

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

# Unbuffered stdout and stderr so development logs appear immediately
ENV PYTHONUNBUFFERED=1
