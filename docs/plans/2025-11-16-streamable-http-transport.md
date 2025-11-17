# Streamable HTTP Transport Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Streamable HTTP transport support to enable remote deployment of the Zammad MCP server alongside Zammad instances in cloud environments.

**Architecture:** Extend the existing FastMCP server to support both stdio (default) and HTTP transports via environment variable configuration. Implement transport selection logic in the main entry point while maintaining backward compatibility with existing stdio-based deployments. Add security considerations and deployment documentation for HTTP mode.

**Tech Stack:** FastMCP 2.3+, Streamable HTTP transport (MCP 2025-03-26), Python 3.10+, environment-based configuration

---

## Task 1: Add Transport Configuration Model

**Files:**
- Create: `mcp_zammad/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Tests for server configuration."""

import os
from mcp_zammad.config import TransportConfig, TransportType


def test_transport_config_defaults():
    """Test default transport configuration."""
    config = TransportConfig()
    assert config.transport == TransportType.STDIO
    assert config.host is None
    assert config.port is None


def test_transport_config_http_from_env(monkeypatch):
    """Test HTTP transport configuration from environment."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8080")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.HTTP
    assert config.host == "0.0.0.0"
    assert config.port == 8080


def test_transport_config_stdio_from_env(monkeypatch):
    """Test stdio transport configuration from environment."""
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")

    config = TransportConfig.from_env()
    assert config.transport == TransportType.STDIO
    assert config.host is None
    assert config.port is None


def test_transport_config_invalid_transport(monkeypatch):
    """Test invalid transport type raises error."""
    monkeypatch.setenv("MCP_TRANSPORT", "invalid")

    try:
        TransportConfig.from_env()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid transport type" in str(e)


def test_transport_config_http_requires_port(monkeypatch):
    """Test HTTP transport requires port."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_PORT", raising=False)

    try:
        config = TransportConfig.from_env()
        config.validate()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "HTTP transport requires MCP_PORT" in str(e)


def test_transport_config_http_defaults_host():
    """Test HTTP transport defaults to localhost."""
    config = TransportConfig(transport=TransportType.HTTP, port=8000)
    config.validate()
    assert config.host == "127.0.0.1"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'mcp_zammad.config'"

**Step 3: Write minimal implementation**

Create `mcp_zammad/config.py`:

```python
"""Configuration for MCP server transport."""

import os
from enum import Enum
from dataclasses import dataclass


class TransportType(str, Enum):
    """Supported transport types."""

    STDIO = "stdio"
    HTTP = "http"


@dataclass
class TransportConfig:
    """Configuration for MCP transport layer.

    Attributes:
        transport: Transport type (stdio or http)
        host: Host address for HTTP transport (default: 127.0.0.1)
        port: Port number for HTTP transport (required for HTTP)
    """

    transport: TransportType = TransportType.STDIO
    host: str | None = None
    port: int | None = None

    @classmethod
    def from_env(cls) -> "TransportConfig":
        """Create configuration from environment variables.

        Environment Variables:
            MCP_TRANSPORT: Transport type (stdio or http, default: stdio)
            MCP_HOST: Host address for HTTP (default: 127.0.0.1)
            MCP_PORT: Port number for HTTP (required if transport=http)

        Returns:
            TransportConfig instance

        Raises:
            ValueError: If transport type is invalid
        """
        transport_str = os.getenv("MCP_TRANSPORT", "stdio").lower()

        try:
            transport = TransportType(transport_str)
        except ValueError:
            raise ValueError(
                f"Invalid transport type: {transport_str}. "
                f"Must be one of: {', '.join(t.value for t in TransportType)}"
            )

        host = os.getenv("MCP_HOST")
        port_str = os.getenv("MCP_PORT")
        port = int(port_str) if port_str else None

        return cls(transport=transport, host=host, port=port)

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.transport == TransportType.HTTP:
            if self.port is None:
                raise ValueError(
                    "HTTP transport requires MCP_PORT environment variable"
                )

            # Default host to localhost for HTTP if not specified
            if self.host is None:
                self.host = "127.0.0.1"
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add mcp_zammad/config.py tests/test_config.py
git commit -m "feat(config): add transport configuration model with env support"
```

---

## Task 2: Update Server Entry Point for Transport Selection

**Files:**
- Modify: `mcp_zammad/__main__.py`
- Modify: `mcp_zammad/server.py:2388-2391`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

Modify `tests/test_main.py` to add HTTP transport tests:

```python
"""Tests for main entry point - ADD TO EXISTING FILE."""

import os
from unittest.mock import Mock, patch


def test_main_with_http_transport(monkeypatch):
    """Test main entry point with HTTP transport."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8000")

    with patch("mcp_zammad.__main__.mcp") as mock_mcp:
        from mcp_zammad.__main__ import main
        main()

        mock_mcp.run.assert_called_once_with(
            transport="http",
            host="127.0.0.1",
            port=8000
        )


def test_main_with_stdio_transport_default(monkeypatch):
    """Test main entry point defaults to stdio transport."""
    # Ensure no transport env vars are set
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.delenv("MCP_PORT", raising=False)

    with patch("mcp_zammad.__main__.mcp") as mock_mcp:
        from mcp_zammad.__main__ import main
        main()

        # Should call run() without transport args (stdio default)
        mock_mcp.run.assert_called_once_with()


def test_main_validates_http_config(monkeypatch):
    """Test main validates HTTP configuration."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    # Don't set port - should fail validation
    monkeypatch.delenv("MCP_PORT", raising=False)

    from mcp_zammad.__main__ import main

    try:
        main()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "HTTP transport requires MCP_PORT" in str(e)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_main.py::test_main_with_http_transport -v`
Expected: FAIL with test assertion errors

**Step 3: Write minimal implementation**

Modify `mcp_zammad/__main__.py`:

```python
"""Entry point for the Zammad MCP server."""

from .server import mcp
from .config import TransportConfig, TransportType


def main() -> None:
    """Run the MCP server with configured transport.

    Transport is configured via environment variables:
    - MCP_TRANSPORT: 'stdio' (default) or 'http'
    - MCP_HOST: Host for HTTP transport (default: 127.0.0.1)
    - MCP_PORT: Port for HTTP transport (required if transport=http)
    """
    # Load transport configuration from environment
    config = TransportConfig.from_env()
    config.validate()

    # FastMCP handles its own async loop
    if config.transport == TransportType.HTTP:
        mcp.run(transport="http", host=config.host, port=config.port)  # type: ignore[func-returns-value]
    else:
        mcp.run()  # type: ignore[func-returns-value]


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_main.py -v`
Expected: PASS (all tests including new HTTP transport tests)

**Step 5: Commit**

```bash
git add mcp_zammad/__main__.py tests/test_main.py
git commit -m "feat(main): add HTTP transport support via environment config"
```

---

## Task 3: Update README with Transport Documentation

**Files:**
- Modify: `README.md:227`
- Modify: `README.md` (add new HTTP deployment section)

**Step 1: Remove outdated statement**

Find line 227 in README.md:
```markdown
**Note**: MCP servers communicate via stdio (stdin/stdout), not HTTP. The `-i` flag is required for interactive mode. Port mapping (`-p 8080:8080`) is not needed for MCP operation.
```

Replace with:
```markdown
**Note**: This server supports both stdio (default) and HTTP transports. For stdio mode, the `-i` flag is required for Docker interactive mode. For HTTP mode, see the HTTP Transport section below.
```

**Step 2: Add HTTP Transport section**

After the Docker installation section (around line 230), add:

```markdown
### HTTP Transport (Remote/Cloud Deployment)

The server supports Streamable HTTP transport for remote deployments alongside your Zammad instance.

#### Environment Configuration

Set these environment variables to enable HTTP transport:

```bash
export MCP_TRANSPORT=http    # Enable HTTP transport
export MCP_HOST=127.0.0.1    # Host to bind (default: 127.0.0.1)
export MCP_PORT=8000         # Port to listen on
```

#### Running with HTTP Transport

**Direct Python:**

```bash
MCP_TRANSPORT=http \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-api-token \
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
```

**Docker:**

```bash
docker run -d \
  --name zammad-mcp-http \
  -p 8000:8000 \
  -e MCP_TRANSPORT=http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8000 \
  -e ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
  -e ZAMMAD_HTTP_TOKEN=your-api-token \
  ghcr.io/basher83/zammad-mcp:latest
```

The MCP endpoint will be available at `http://localhost:8000/mcp/`.

#### Client Configuration for HTTP

Configure your MCP client to use HTTP transport:

```json
{
  "mcpServers": {
    "zammad": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

#### Security Considerations

⚠️ **Important Security Notes:**

1. **Local Development**: Use `MCP_HOST=127.0.0.1` (localhost only)
2. **Production**: Implement authentication (see Security section)
3. **HTTPS**: Use reverse proxy (nginx/caddy) for TLS/HTTPS
4. **Firewall**: Restrict access to trusted networks only
5. **Origin Validation**: Built-in protection against DNS rebinding attacks

For production deployments, see [Security](#security) section.
```

**Step 3: Update Environment Variables section**

Find the Environment Variables section and add HTTP transport variables:

```markdown
#### Transport Configuration (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio` or `http` |
| `MCP_HOST` | `127.0.0.1` | Host address for HTTP transport |
| `MCP_PORT` | - | Port number for HTTP transport (required if `MCP_TRANSPORT=http`) |
```

**Step 4: Verify changes**

Run: `mise run markdown-lint`
Expected: PASS (no linting errors)

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs(readme): add HTTP transport documentation and update stdio note"
```

---

## Task 4: Add HTTP Deployment Guide

**Files:**
- Create: `docs/deployment/http-transport.md`

**Step 1: Create deployment guide**

Create `docs/deployment/http-transport.md`:

```markdown
# HTTP Transport Deployment Guide

This guide covers deploying the Zammad MCP server using HTTP transport for remote access and cloud deployments.

## Overview

The Streamable HTTP transport enables:
- **Remote Access**: Connect from different machines/networks
- **Multi-Client**: Handle multiple concurrent client connections
- **Cloud Deployment**: Run on VPS, containers, serverless platforms
- **Co-location**: Host alongside your Zammad instance

## Quick Start

### Local Development

```bash
# Start server on localhost only
MCP_TRANSPORT=http \
MCP_PORT=8000 \
ZAMMAD_URL=https://instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-token \
mcp-zammad
```

Server available at: `http://127.0.0.1:8000/mcp/`

### Docker Deployment

```bash
docker run -d \
  --name zammad-mcp \
  -p 8000:8000 \
  -e MCP_TRANSPORT=http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8000 \
  -e ZAMMAD_URL=https://instance.zammad.com/api/v1 \
  -e ZAMMAD_HTTP_TOKEN=your-token \
  ghcr.io/basher83/zammad-mcp:latest
```

## Production Deployment

### 1. Security Setup

#### Environment Variables

Create `.env` file:

```bash
# Transport
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1  # Bind to localhost - use reverse proxy
MCP_PORT=8000

# Zammad
ZAMMAD_URL=https://your-instance.zammad.com/api/v1
ZAMMAD_HTTP_TOKEN=your-api-token
```

#### Reverse Proxy (nginx)

Create `/etc/nginx/sites-available/zammad-mcp`:

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp/ {
        proxy_pass http://127.0.0.1:8000/mcp/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/zammad-mcp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 2. Systemd Service

Create `/etc/systemd/system/zammad-mcp.service`:

```ini
[Unit]
Description=Zammad MCP Server (HTTP)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/zammad-mcp
EnvironmentFile=/opt/zammad-mcp/.env
ExecStart=/usr/local/bin/uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable zammad-mcp
sudo systemctl start zammad-mcp
sudo systemctl status zammad-mcp
```

### 3. Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  zammad-mcp:
    image: ghcr.io/basher83/zammad-mcp:latest
    container_name: zammad-mcp
    restart: unless-stopped
    environment:
      MCP_TRANSPORT: http
      MCP_HOST: 0.0.0.0
      MCP_PORT: 8000
      ZAMMAD_URL: ${ZAMMAD_URL}
      ZAMMAD_HTTP_TOKEN: ${ZAMMAD_HTTP_TOKEN}
    ports:
      - "127.0.0.1:8000:8000"  # Bind to localhost only
    networks:
      - zammad-network

networks:
  zammad-network:
    external: true  # Use same network as Zammad instance
```

Run:

```bash
docker-compose up -d
docker-compose logs -f zammad-mcp
```

## Cloud Platforms

### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/zammad-mcp

# Deploy
gcloud run deploy zammad-mcp \
  --image gcr.io/PROJECT_ID/zammad-mcp \
  --platform managed \
  --region us-central1 \
  --set-env-vars MCP_TRANSPORT=http,MCP_HOST=0.0.0.0,MCP_PORT=8080 \
  --set-secrets ZAMMAD_URL=zammad-url:latest,ZAMMAD_HTTP_TOKEN=zammad-token:latest \
  --allow-unauthenticated  # Configure authentication separately
```

### AWS ECS/Fargate

Task definition JSON:

```json
{
  "family": "zammad-mcp",
  "containerDefinitions": [{
    "name": "zammad-mcp",
    "image": "ghcr.io/basher83/zammad-mcp:latest",
    "environment": [
      {"name": "MCP_TRANSPORT", "value": "http"},
      {"name": "MCP_HOST", "value": "0.0.0.0"},
      {"name": "MCP_PORT", "value": "8000"}
    ],
    "secrets": [
      {"name": "ZAMMAD_URL", "valueFrom": "arn:aws:secretsmanager:..."},
      {"name": "ZAMMAD_HTTP_TOKEN", "valueFrom": "arn:aws:secretsmanager:..."}
    ],
    "portMappings": [{
      "containerPort": 8000,
      "protocol": "tcp"
    }]
  }]
}
```

## Security Best Practices

### 1. Authentication

MCP HTTP transport requires client authentication. Options:

- **API Keys**: Use HTTP headers
- **OAuth 2.0**: Token-based authentication
- **mTLS**: Certificate-based authentication

### 2. Network Security

- **Firewall Rules**: Whitelist trusted IP addresses
- **VPN**: Deploy in private network, access via VPN
- **Service Mesh**: Use Istio/Linkerd for zero-trust networking

### 3. Monitoring

```bash
# Health check endpoint
curl http://localhost:8000/health

# Metrics (if implemented)
curl http://localhost:8000/metrics
```

## Troubleshooting

### Connection Refused

```bash
# Check if server is running
ps aux | grep mcp-zammad

# Check port binding
netstat -tlnp | grep 8000

# Check logs
journalctl -u zammad-mcp -f
```

### CORS Issues

If using web clients, configure CORS in reverse proxy:

```nginx
add_header Access-Control-Allow-Origin https://your-client.com;
add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
add_header Access-Control-Allow-Headers "Content-Type, Accept";
```

### Performance

- **Connection Pooling**: Clients should reuse connections
- **Load Balancing**: Use multiple instances behind load balancer
- **Caching**: Implement HTTP caching headers

## Client Configuration

### Claude Desktop (HTTP)

```json
{
  "mcpServers": {
    "zammad": {
      "url": "https://mcp.your-domain.com/mcp/"
    }
  }
}
```

### Custom Client

```python
from mcp import ClientSession
from mcp.client.streamable_http import StreamableHTTPTransport

async with ClientSession(
    StreamableHTTPTransport("http://localhost:8000/mcp/")
) as session:
    result = await session.call_tool("zammad_search_tickets", {
        "query": "status:open"
    })
```

## See Also

- [MCP Specification - Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [Security Guide](../security.md)
- [Docker Deployment](./docker.md)
```

**Step 2: Create directory if needed**

Run: `mkdir -p docs/deployment`

**Step 3: Verify markdown**

Run: `mise run markdown-lint`
Expected: PASS

**Step 4: Commit**

```bash
git add docs/deployment/http-transport.md
git commit -m "docs(deployment): add comprehensive HTTP transport deployment guide"
```

---

## Task 5: Update .env.example with Transport Variables

**Files:**
- Modify: `.env.example`

**Step 1: Add transport configuration**

Add to `.env.example`:

```bash
# === Transport Configuration ===

# Transport type: stdio (default) or http
# MCP_TRANSPORT=stdio

# HTTP Transport Settings (required if MCP_TRANSPORT=http)
# Host to bind to (default: 127.0.0.1)
# MCP_HOST=127.0.0.1

# Port to listen on (required for HTTP transport)
# MCP_PORT=8000
```

**Step 2: Verify format**

Run: `cat .env.example`
Expected: Clean formatting, commented examples

**Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(env): add HTTP transport configuration examples"
```

---

## Task 6: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Add unreleased changes**

Run: `mise run changelog`

Expected: Updates unreleased section with recent commits

**Step 2: Review changes**

Run: `git diff CHANGELOG.md`
Expected: Shows HTTP transport feature additions

**Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): update for HTTP transport feature"
```

---

## Task 7: Add Integration Tests for HTTP Transport

**Files:**
- Create: `tests/integration/test_http_transport.py`
- Modify: `pyproject.toml` (add pytest-asyncio if not present)

**Step 1: Write integration test**

Create `tests/integration/test_http_transport.py`:

```python
"""Integration tests for HTTP transport."""

import os
import time
import subprocess
import httpx
import pytest


@pytest.fixture
def http_server():
    """Start HTTP server for integration testing."""
    env = os.environ.copy()
    env.update({
        "MCP_TRANSPORT": "http",
        "MCP_HOST": "127.0.0.1",
        "MCP_PORT": "8765",
        "ZAMMAD_URL": "http://mock.zammad.com/api/v1",
        "ZAMMAD_HTTP_TOKEN": "test-token",
    })

    # Start server process
    process = subprocess.Popen(
        ["python", "-m", "mcp_zammad"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(2)

    yield "http://127.0.0.1:8765"

    # Cleanup
    process.terminate()
    process.wait(timeout=5)


@pytest.mark.integration
def test_http_server_starts(http_server):
    """Test that HTTP server starts and responds."""
    response = httpx.get(f"{http_server}/health", timeout=5.0)
    assert response.status_code == 200


@pytest.mark.integration
def test_mcp_endpoint_exists(http_server):
    """Test that MCP endpoint is accessible."""
    # MCP endpoint should accept POST requests
    response = httpx.post(
        f"{http_server}/mcp/",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers={"Accept": "application/json, text/event-stream"},
        timeout=10.0,
    )
    assert response.status_code in [200, 400, 405]  # Server should respond


@pytest.mark.integration
def test_http_server_rejects_missing_port():
    """Test that server fails without port in HTTP mode."""
    env = os.environ.copy()
    env.update({
        "MCP_TRANSPORT": "http",
        "MCP_HOST": "127.0.0.1",
    })
    env.pop("MCP_PORT", None)  # Remove port

    process = subprocess.Popen(
        ["python", "-m", "mcp_zammad"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Should exit with error
    process.wait(timeout=5)
    assert process.returncode != 0

    stderr = process.stderr.read().decode()
    assert "HTTP transport requires MCP_PORT" in stderr
```

**Step 2: Run tests to verify they fail initially**

Run: `python3 -m pytest tests/integration/test_http_transport.py -v -m integration`
Expected: Tests may fail if server doesn't expose /health endpoint

**Step 3: Add health endpoint if needed**

If tests fail due to missing /health endpoint, add to `mcp_zammad/server.py`:

```python
# Add after mcp initialization (around line 864)
@mcp.custom_route("/health", methods=["GET"])
async def health_check():
    """Health check endpoint for HTTP transport."""
    return {"status": "healthy", "transport": "http"}
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/integration/test_http_transport.py -v -m integration`
Expected: PASS (all integration tests)

**Step 5: Commit**

```bash
git add tests/integration/test_http_transport.py
git commit -m "test(integration): add HTTP transport integration tests"
```

---

## Task 8: Update GitHub Issue #113

**Files:**
- None (GitHub API interaction)

**Step 1: Test HTTP transport manually**

```bash
# Start server
MCP_TRANSPORT=http MCP_PORT=8000 \
ZAMMAD_URL=http://demo.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=test \
python -m mcp_zammad

# In another terminal, test endpoint
curl http://127.0.0.1:8000/health
```

Expected: `{"status": "healthy", "transport": "http"}`

**Step 2: Comment on issue**

Run:
```bash
gh issue comment 113 --body "✅ Streamable HTTP transport has been implemented!

**Changes:**
- Added HTTP transport support via environment variables
- Maintained backward compatibility (stdio is default)
- Added comprehensive deployment documentation
- Included security best practices

**Usage:**
\`\`\`bash
MCP_TRANSPORT=http MCP_PORT=8000 \\
ZAMMAD_URL=https://instance.zammad.com/api/v1 \\
ZAMMAD_HTTP_TOKEN=token \\
mcp-zammad
\`\`\`

**Documentation:**
- [README HTTP Transport Section](../blob/main/README.md#http-transport-remotec loud-deployment)
- [HTTP Deployment Guide](../blob/main/docs/deployment/http-transport.md)

You can now host this MCP server alongside your Zammad instance! 🎉"
```

**Step 3: Close issue**

Run: `gh issue close 113 --reason completed`

Expected: Issue #113 closed

---

## Task 9: Create Pull Request (if using feature branch)

**Files:**
- None (Git operations)

**Step 1: Push feature branch**

Run: `git push -u origin feature/http-transport`

**Step 2: Create PR**

Run:
```bash
gh pr create \
  --title "feat: add Streamable HTTP transport support" \
  --body "## Overview

Implements Streamable HTTP transport support to enable remote deployment of the Zammad MCP server.

Closes #113

## Changes

- ✨ Add transport configuration model with environment variable support
- ✨ Update server entry point to support both stdio and HTTP transports
- 📚 Add comprehensive HTTP deployment documentation
- 🧪 Add integration tests for HTTP transport
- 🔒 Include security considerations and best practices

## Configuration

New environment variables:
- \`MCP_TRANSPORT\`: Transport type (stdio/http, default: stdio)
- \`MCP_HOST\`: Host address for HTTP (default: 127.0.0.1)
- \`MCP_PORT\`: Port number for HTTP (required if transport=http)

## Testing

\`\`\`bash
# Unit tests
pytest tests/test_config.py tests/test_main.py -v

# Integration tests
pytest tests/integration/test_http_transport.py -v -m integration
\`\`\`

## Documentation

- Updated README with HTTP transport section
- Added \`docs/deployment/http-transport.md\` with deployment examples
- Updated \`.env.example\` with transport configuration

## Backward Compatibility

✅ Fully backward compatible - stdio remains the default transport" \
  --label enhancement \
  --label documentation
```

**Step 3: Verify PR**

Run: `gh pr view --web`

Expected: Opens PR in browser for review

---

## Verification Steps

After all tasks complete:

1. **Run full test suite:**
   ```bash
   pytest --cov=mcp_zammad --cov-report=term-missing
   ```
   Expected: >87% coverage, all tests pass

2. **Test stdio transport (backward compat):**
   ```bash
   echo '{"method":"test"}' | python -m mcp_zammad
   ```
   Expected: Server runs in stdio mode

3. **Test HTTP transport:**
   ```bash
   MCP_TRANSPORT=http MCP_PORT=8000 python -m mcp_zammad &
   sleep 2
   curl http://127.0.0.1:8000/health
   ```
   Expected: `{"status": "healthy"}`

4. **Test validation:**
   ```bash
   MCP_TRANSPORT=http python -m mcp_zammad
   ```
   Expected: Error "HTTP transport requires MCP_PORT"

5. **Lint checks:**
   ```bash
   ./scripts/quality-check.sh
   ```
   Expected: All checks pass

---

## Rollback Plan

If issues arise:

```bash
# Revert to main branch
git checkout main

# Or revert specific commits
git revert <commit-sha>

# Or delete feature branch
git branch -D feature/http-transport
git push origin --delete feature/http-transport
```

---

## Future Enhancements

Post-implementation considerations:

1. **Authentication**: Add API key authentication for HTTP transport
2. **Rate Limiting**: Implement rate limiting for HTTP endpoints
3. **Metrics**: Add Prometheus metrics endpoint
4. **WebSocket**: Consider WebSocket transport as alternative
5. **Load Balancing**: Document multi-instance deployment patterns

---

## References

- [MCP Streamable HTTP Specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [FastMCP HTTP Transport Docs](https://gofastmcp.com/deployment/running-server)
- [Issue #113](https://github.com/basher83/Zammad-MCP/issues/113)
