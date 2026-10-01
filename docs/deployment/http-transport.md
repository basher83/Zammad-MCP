# HTTP Transport Deployment Guide

This guide covers deploying the Zammad MCP server using HTTP transport for remote access and cloud deployments.

## Overview

The Streamable HTTP transport enables:

- **Remote Access**: Connect from different machines/networks
- **Multi-Client**: Handle multiple concurrent client connections
- **Cloud Deployment**: Run on VPS, containers, serverless platforms
- **Co-location**: Host alongside your Zammad instance

## Environment Configuration

Set these environment variables to enable HTTP transport:

```bash
export MCP_TRANSPORT=http    # Enable HTTP transport
export MCP_HOST=127.0.0.1    # Host to bind (default: 127.0.0.1)
export MCP_PORT=8000         # Port to listen on (required)
```

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio` or `http` |
| `MCP_HOST` | `127.0.0.1` | Host address for HTTP transport |
| `MCP_PORT` | - | Port number for HTTP transport (required if `MCP_TRANSPORT=http`) |

The [configuration reference](../reference/configuration.md) lists every variable, including the Zammad credentials.

## Quick Start

### Local Development

The commands below run the server with `uvx`, as in the README [installation](../../README.md#installation).
If you installed the package into an environment, replace the `uvx` line with `mcp-zammad`.

```bash
# Start server on localhost only
MCP_TRANSPORT=http \
MCP_HOST=127.0.0.1 \
MCP_PORT=8000 \
ZAMMAD_URL=https://instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-token \
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
```

Server available at: `http://127.0.0.1:8000/mcp`

Check that the listener runs:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"healthy","transport":"http"}
```

This check proves only that the HTTP listener runs. It does not prove that the server can reach Zammad.

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

Access the MCP endpoint at `http://localhost:8000/mcp`.
`MCP_HOST=0.0.0.0` inside the container is required for Docker port publishing.
The `-p 8000:8000` mapping publishes the port on all host interfaces. Read the
[Production Deployment](#production-deployment) warning before you expose it beyond localhost.

## Production Deployment

> **Security requirement:** The server does not implement inbound MCP client authentication. `ZAMMAD_*`
> credentials authenticate only to Zammad. They do not authenticate MCP clients. Keep the listener on loopback
> or a private trusted network until an authenticated TLS proxy or equivalent access control is in place.
> Bind to `0.0.0.0` only behind an authenticated TLS proxy or inside a network restricted to trusted clients.

Use a reverse proxy for TLS and client authentication. The nginx and Caddy examples below provide TLS only.
Add an authentication policy appropriate for your environment before you expose the server outside a trusted network.

**Production checklist:**

1. Use `MCP_HOST=0.0.0.0` only behind a reverse proxy
2. Enable HTTPS/TLS via reverse proxy
3. Implement authentication at the proxy or application layer
4. Restrict access with firewall rules

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

    location = /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Streamable HTTP responses
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # Zammad webhook ingress (optional, see Webhook events below)
    location = /webhooks/zammad {
        proxy_pass http://127.0.0.1:8000/webhooks/zammad;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Webhooks:** The server accepts Zammad webhook deliveries at `POST /webhooks/zammad`. Set
`ZAMMAD_WEBHOOK_SECRET` to the HMAC SHA1 Signature Token of the Zammad webhook. The route returns `503` until
you set the secret. A missing or invalid `X-Hub-Signature` header returns `401`. Omit the `/webhooks/zammad`
location if you do not use webhooks. See [Webhook events](#webhook-events) for the Zammad setup.

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/zammad-mcp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### Reverse Proxy (Caddy)

Caddy requests and renews TLS certificates automatically. This example provides TLS only.

Start the MCP server. The server binds to all interfaces here because the proxy connects to it over the network:

```bash
MCP_TRANSPORT=http \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-api-token \
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
```

If Caddy runs on the same host, keep `MCP_HOST=127.0.0.1` instead.

**Caddyfile configuration:**

```caddy
mcp.yourdomain.com {
    reverse_proxy localhost:8000
    # Caddy automatically handles HTTPS/TLS
}
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

The following is a hardened illustrative Compose configuration. It differs from the checked-in development
`docker-compose.yml`, which publishes host port 9146 on all interfaces.

```yaml
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

Configure Cloud Run IAM for the intended clients. Do not add `--allow-unauthenticated`.

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/zammad-mcp

# Deploy
gcloud run deploy zammad-mcp \
  --image gcr.io/PROJECT_ID/zammad-mcp \
  --platform managed \
  --region us-central1 \
  --set-env-vars MCP_TRANSPORT=http,MCP_HOST=0.0.0.0,MCP_PORT=8080 \
  --set-secrets ZAMMAD_URL=zammad-url:latest,ZAMMAD_HTTP_TOKEN=zammad-token:latest
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

## Webhook events

Instead of repeatedly searching for changed tickets, Zammad can push ticket events to the server, and MCP clients poll
them with `zammad_list_events`. This needs `MCP_TRANSPORT=http`. Stdio mode has no inbound listener.

1. **Configure a secret** (the endpoint answers `503` until it is set):

   ```bash
   export ZAMMAD_WEBHOOK_SECRET="$(openssl rand -hex 32)"
   ```

2. **Expose `POST /webhooks/zammad`** to your Zammad instance, behind TLS (reverse proxy). The signature proves the
   payload came from Zammad but does not encrypt it.

3. **Create the webhook in Zammad** (admin only): *Manage → Webhooks → New Webhook*
   - Endpoint: `https://your-mcp-host/webhooks/zammad`
   - HMAC SHA1 Signature Token: the same value as `ZAMMAD_WEBHOOK_SECRET`
   - Keep the default JSON payload (the server reads `ticket.id`, `ticket.number`, `ticket.article_count`,
     `ticket.updated_at`, and `article.id`)

4. **Create a trigger** (*Manage → Triggers → New Trigger*) that fires on the ticket actions you care about and executes
   the webhook.

The server maps deliveries to `ticket.create` (first article), `ticket.article.create` (later articles), or
`ticket.update` (no article in payload). Invalid or missing `X-Hub-Signature` headers return `401`. Non-ticket or
malformed payloads return `400`. Accepted deliveries return `202`, and the server keeps the
`X-Zammad-Trigger` header value as the event `trigger`. Only identifiers and timestamps are retained. Article bodies
are never retained.

Retention is process-local and bounded (1000 events, oldest evicted first) and is lost on restart. Poll with
`zammad_list_events`, which returns the oldest events after `since` first (up to `limit`). Pass the returned
`next_since` as `since` on the next call and repeat until `events` is empty. Then fetch details with
`zammad_get_ticket`.

## Security Best Practices

### 1. Authentication

MCP HTTP transport requires client authentication for remote deployment. The server does not implement these options.
Configure one at a proxy, service mesh, or platform boundary:

- **API Keys**: Use HTTP headers
- **OAuth 2.0**: Token-based authentication
- **mTLS**: Certificate-based authentication

### 2. Network Security

- **Local Development**: Use `MCP_HOST=127.0.0.1` (localhost only)
- **Firewall Rules**: Whitelist trusted IP addresses
- **VPN**: Deploy in private network, access via VPN
- **Service Mesh**: Use Istio/Linkerd for zero-trust networking
- **Host/Origin Validation**: Configure this at the authenticated proxy. The server does not add it automatically

### 3. Monitoring

```bash
# Health check endpoint
curl http://localhost:8000/health
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

The MCP endpoint is `/mcp` on the configured host and port, for example `http://localhost:8000/mcp` or
`https://mcp.your-domain.com/mcp`. How a client accepts that URL depends on the client.

### Claude Desktop and claude.ai (HTTP)

Claude Desktop and claude.ai add remote MCP servers through the Connectors settings, not through
`claude_desktop_config.json`. The documented steps on 2026-10-01 are:

1. Open Settings and click **Connectors**.
2. Click **Add**, then **Add custom connector**.
3. Enter the server URL, for example `https://mcp.your-domain.com/mcp`, and click **Add**.
4. Complete the authentication that your proxy requires.

The connector must reach the server over the internet, so this path needs the
[production deployment](#production-deployment) with TLS and authentication.
`claude_desktop_config.json` documents only local `command` and `args` servers.

### Claude Code (HTTP)

Claude Code accepts an HTTP server URL on the command line:

```bash
claude mcp add --transport http zammad https://mcp.your-domain.com/mcp
```

The equivalent `.mcp.json` entry sets `type` to `http`. An entry with a `url` but no `type` is read as a stdio server.

```json
{
  "mcpServers": {
    "zammad": {
      "type": "http",
      "url": "https://mcp.your-domain.com/mcp"
    }
  }
}
```

### Custom Client

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async with streamable_http_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("zammad_search_tickets", {"query": "status:open"})
```

## See Also

- [MCP Specification - Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [Configuration reference](../reference/configuration.md)
- [Security Guide](../../SECURITY.md)
