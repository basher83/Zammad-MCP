FROM python:3.13-slim

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY mcp_zammad/ ./mcp_zammad/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Create entrypoint
EXPOSE 8080
CMD ["uv", "run", "mcp-zammad"]
