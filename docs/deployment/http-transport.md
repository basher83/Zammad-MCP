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
