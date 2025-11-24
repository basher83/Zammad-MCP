# Zammad MCP Server

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/basher83/Zammad-MCP?utm_source=oss&utm_medium=github&utm_campaign=basher83%2FZammad-MCP&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/9cc0ebac926a4d56b0bdf2271d46bbf7)](https://app.codacy.com/gh/basher83/Zammad-MCP/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
![Coverage](https://img.shields.io/badge/coverage-90.08%25-brightgreen)

An MCP server that connects AI assistants to Zammad, providing tools for managing tickets, users, organizations, and attachments.

> **Disclaimer**: This project is not affiliated with or endorsed by Zammad GmbH or the Zammad Foundation. This is an independent integration that uses the Zammad API.

## Features

### Tools

- **Ticket Management**
  - `zammad_search_tickets` - Search tickets with multiple filters
  - `zammad_get_ticket` - Get detailed ticket information with articles (supports pagination)
  - `zammad_create_ticket` - Create new tickets
  - `zammad_update_ticket` - Update ticket properties
  - `zammad_add_article` - Add comments/notes to tickets
  - `zammad_add_ticket_tag` / `zammad_remove_ticket_tag` - Manage ticket tags

- **Attachment Support**
  - `zammad_get_article_attachments` - List attachments for a ticket article
  - `zammad_download_attachment` - Download attachment content (base64-encoded)
  - `zammad_delete_attachment` - Delete attachments from ticket articles

- **User & Organization Management**
  - `zammad_get_user` / `zammad_search_users` - User information and search
  - `zammad_get_organization` / `zammad_search_organizations` - Organization data
  - `zammad_get_current_user` - Get authenticated user info

- **System Information**
  - `zammad_list_groups` - Get all available groups (cached for performance)
  - `zammad_list_ticket_states` - Get all ticket states (cached for performance)
  - `zammad_list_ticket_priorities` - Get all priority levels (cached for performance)
  - `zammad_get_ticket_stats` - Get ticket statistics (optimized with pagination)

### Resources

Access Zammad data directly:

- `zammad://ticket/{id}` - Individual ticket details
- `zammad://user/{id}` - User profile information
- `zammad://organization/{id}` - Organization details
- `zammad://queue/{group}` - Ticket queue for a group

### Prompts

Pre-configured prompts:

- `analyze_ticket` - Comprehensive ticket analysis
- `draft_response` - Generate ticket responses
- `escalation_summary` - Summarize escalated tickets

## Installation

### Option 1: Run Directly with uvx (Recommended)

Run without installation:

```bash
# Install uv if you haven't already
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Run directly from GitHub
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad

# Or with environment variables
ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-api-token \
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
```

### Option 2: Docker Run

For production or containerized deployments:

```bash
# Basic usage with environment variables
docker run --rm -i \
  -e ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
  -e ZAMMAD_HTTP_TOKEN=your-api-token \
  ghcr.io/basher83/zammad-mcp:latest

# Using Docker secrets for better security
docker run --rm -i \
  -e ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
  -e ZAMMAD_HTTP_TOKEN_FILE=/run/secrets/token \
  -v ./secrets/zammad_http_token.txt:/run/secrets/token:ro \
  ghcr.io/basher83/zammad-mcp:latest

# With .env file
docker run --rm -i \
  --env-file .env \
  ghcr.io/basher83/zammad-mcp:latest
```

#### Docker Image Versioning

The project publishes Docker images with semantic versioning:

- `latest` - Most recent stable release
- `1.2.3` - Specific version (recommended for production)
- `1.2` - Latest patch of 1.2 minor release
- `1` - Latest minor/patch of 1.x major release
- `main` - Latest main branch (may be unstable)

```bash
# Recommended for production - pin to specific version
docker pull ghcr.io/basher83/zammad-mcp:1.0.0
```

View all versions on [GitHub Container Registry](https://github.com/basher83/Zammad-MCP/pkgs/container/zammad-mcp).

### Option 3: For Developers

To contribute or modify the code:

```bash
# Clone the repository
git clone https://github.com/basher83/zammad-mcp.git
cd zammad-mcp

# Run the setup script
# On macOS/Linux:
./setup.sh

# On Windows (PowerShell):
.\setup.ps1
```

For manual setup, see the [Development](#development) section below.

## Configuration

The server requires Zammad API credentials. Use a `.env` file:

1. Copy the example configuration:

   ```bash
   cp .env.example .env
   ```

1. Edit `.env` with your Zammad credentials:

   ```env
   # Required: Zammad instance URL (include /api/v1)
   ZAMMAD_URL=https://your-instance.zammad.com/api/v1

   # Authentication (choose one method):
   # Option 1: API Token (recommended)
   ZAMMAD_HTTP_TOKEN=your-api-token

   # Option 2: OAuth2 Token
   # ZAMMAD_OAUTH2_TOKEN=your-oauth2-token

   # Option 3: Username/Password
   # ZAMMAD_USERNAME=your-username
   # ZAMMAD_PASSWORD=your-password

   # Optional: Logging level (default: INFO)
   # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
   # LOG_LEVEL=INFO

   # Optional: Transport Configuration
   # MCP_TRANSPORT=stdio  # Transport type: stdio (default) or http
   # MCP_HOST=127.0.0.1   # Host address for HTTP transport
   # MCP_PORT=8000        # Port number for HTTP transport
   ```

1. The server will automatically load the `.env` file on startup.

### Transport Configuration (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio` or `http` |
| `MCP_HOST` | `127.0.0.1` | Host address for HTTP transport |
| `MCP_PORT` | - | Port number for HTTP transport (required if `MCP_TRANSPORT=http`) |

**Important**: Keep your `.env` file out of version control (already in `.gitignore`).

## Response Formats

All data-returning tools support two output formats:

- **Markdown** (default): Human-readable format optimized for LLM consumption
- **JSON**: Machine-readable format with complete metadata

Example:

```python
# Markdown (default)
zammad_search_tickets(query="network", response_format="markdown")

# JSON
zammad_search_tickets(query="network", response_format="json")
```

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "zammad": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/basher83/zammad-mcp.git", "mcp-zammad"],
      "env": {
        "ZAMMAD_URL": "https://your-instance.zammad.com/api/v1",
        "ZAMMAD_HTTP_TOKEN": "your-api-token"
      }
    }
  }
}
```

Or using Docker:

```json
{
  "mcpServers": {
    "zammad": {
      "command": "docker",
      "args": ["run", "--rm", "-i", 
               "-e", "ZAMMAD_URL=https://your-instance.zammad.com/api/v1",
               "-e", "ZAMMAD_HTTP_TOKEN=your-api-token",
               "ghcr.io/basher83/zammad-mcp:latest"]
    }
  }
}
```

**Note**: The server supports stdio (default) and HTTP transports. Stdio mode requires the `-i` flag for Docker. See the HTTP Transport section below for remote deployments.

**Important**: The `-i` flag is required—without it, the MCP server cannot receive stdin. Preserve this flag in wrapper scripts or shell aliases.

Or if you have it installed locally:

```json
{
  "mcpServers": {
    "zammad": {
      "command": "python",
      "args": ["-m", "mcp_zammad"],
      "env": {
        "ZAMMAD_URL": "https://your-instance.zammad.com/api/v1",
        "ZAMMAD_HTTP_TOKEN": "your-api-token"
      }
    }
  }
}
```

### Standalone Usage

```bash
# Run the server
python -m mcp_zammad

# Or with environment variables
ZAMMAD_URL=https://instance.zammad.com/api/v1 ZAMMAD_HTTP_TOKEN=token python -m mcp_zammad
```

### HTTP Transport (Remote/Cloud Deployment)

The server supports Streamable HTTP transport for remote deployments.

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
MCP_HOST=127.0.0.1 \
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

Access the MCP endpoint at `http://localhost:8000/mcp/`.

#### Production Deployment with Reverse Proxy

⚠️ **SECURITY WARNING**: Bind to `0.0.0.0` only behind a reverse proxy with TLS.

Use a reverse proxy (nginx/Caddy) for HTTPS and security:

**Example with Caddy:**

```bash
# Start the MCP server (binds to all interfaces for reverse proxy)
MCP_TRANSPORT=http \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-api-token \
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
```

**Caddyfile configuration:**

```caddy
mcp.yourdomain.com {
    reverse_proxy localhost:8000
    # Caddy automatically handles HTTPS/TLS
}
```

**Production checklist:**

1. Use `MCP_HOST=0.0.0.0` only behind a reverse proxy
2. Enable HTTPS/TLS via reverse proxy
3. Implement authentication at the proxy or application layer
4. Restrict access with firewall rules

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

1. **Local Development**: Use `MCP_HOST=127.0.0.1` (localhost only)
2. **Production**: Implement authentication (see [Security](#security))
3. **HTTPS**: Use reverse proxy for TLS
4. **Firewall**: Restrict access to trusted networks
5. **DNS Rebinding**: Built-in origin validation protects against these attacks

## Examples

### Search for Open Tickets

```plaintext
Use search_tickets with state="open" to find all open tickets
```

### Create a Support Ticket

```plaintext
Use create_ticket with:
- title: "Customer needs help with login"
- group: "Support"
- customer: "customer@example.com"
- article_body: "Customer reported unable to login..."
```

### Update and Respond to a Ticket

```plaintext
1. Use get_ticket with ticket_id=123 to see the full conversation
2. Use add_article to add your response
3. Use update_ticket to change state to "pending reminder"
```

### Analyze Escalated Tickets

```plaintext
Use the escalation_summary prompt to get a report of all tickets approaching escalation
```

### Upload Attachments to a Ticket

```plaintext
Use add_article with attachments parameter:
- ticket_id: 123
- body: "See attached documentation"
- attachments: [
    {
      "filename": "guide.pdf",
      "data": "JVBERi0xLjQKJ...",  # base64-encoded content
      "mime_type": "application/pdf"
    }
  ]
```

### Delete an Attachment

```plaintext
Use delete_attachment with:
- ticket_id: 123
- article_id: 456
- attachment_id: 789
```

## Development

### Setup

#### Using Setup Scripts (Recommended)

```bash
# Clone the repository
git clone https://github.com/basher83/zammad-mcp.git
cd zammad-mcp

# Run the setup script
# On macOS/Linux:
./setup.sh

# On Windows (PowerShell):
.\setup.ps1
```

#### Manual Setup

```bash
# Clone the repository
git clone https://github.com/basher83/zammad-mcp.git
cd zammad-mcp

# Create a virtual environment with uv
uv venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install in development mode
uv pip install -e ".[dev]"
```

### Project Structure

```plaintext
zammad-mcp/
├── mcp_zammad/
│   ├── __init__.py
│   ├── __main__.py
│   ├── server.py      # MCP server implementation
│   ├── client.py      # Zammad API client wrapper
│   └── models.py      # Pydantic models
├── tests/
├── scripts/
│   └── uv/            # UV single-file scripts
├── pyproject.toml
├── README.md
├── Dockerfile
└── .env.example
```

### Running Tests

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_zammad
```

### Code Quality

```bash
# Format code
uv run ruff format mcp_zammad tests

# Lint
uv run ruff check mcp_zammad tests

# Type checking
uv run mypy mcp_zammad

# Run all quality checks
./scripts/quality-check.sh
```

## API Token Generation

To generate an API token in Zammad:

1. Log into your Zammad instance
1. Click on your avatar → Profile
1. Navigate to "Token Access"
1. Click "Create"
1. Name your token (e.g., "MCP Server")
1. Select appropriate permissions
1. Copy the generated token

## Troubleshooting

### Connection Issues

- Verify your Zammad URL includes the protocol (https://)
- Check that your API token has the necessary permissions
- Ensure your Zammad instance is accessible from your network

### Authentication Errors

- Use API tokens over username/password
- Ensure tokens have permissions for the operations
- Check token expiration in Zammad settings

### Rate Limiting

The server respects Zammad's rate limits. If you hit rate limits:

- Reduce request frequency
- Paginate large result sets
- Cache frequently accessed data

## Security

The server implements multiple layers of protection following industry best practices.

### Reporting Security Issues

**⚠️ IMPORTANT**: Do not create public GitHub issues for security vulnerabilities.

Report via [GitHub Security Advisories](https://github.com/basher83/Zammad-MCP/security/advisories/new) (preferred) or see [SECURITY.md](SECURITY.md).

### Security Features

- ✅ **Input Validation**: Validates and sanitizes all user inputs ([models.py](mcp_zammad/models.py))
- ✅ **SSRF Protection**: URL validation prevents server-side request forgery ([client.py](mcp_zammad/client.py#L46-L58))
- ✅ **XSS Prevention**: Sanitizes HTML in all text fields ([models.py](mcp_zammad/models.py#L27-L31))
- ✅ **Secure Authentication**: Prefers API tokens over passwords ([client.py](mcp_zammad/client.py#L60-L92))
- ✅ **Dependency Scanning**: Dependabot detects vulnerabilities automatically
- ✅ **Security Testing**: CI runs Bandit, Safety, and pip-audit ([security-scan.yml](.github/workflows/security-scan.yml))

See [SECURITY.md](SECURITY.md) for complete documentation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code standards, testing, and pull request guidelines.

## License

[AGPL-3.0-or-later](LICENSE) — matches the [Zammad project](https://github.com/zammad/zammad) license.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical design
- [SECURITY.md](SECURITY.md) — Security policy
- [CONTRIBUTING.md](CONTRIBUTING.md) — Development guidelines
- [CHANGELOG.md](CHANGELOG.md) — Version history

## Support

- [GitHub Issues](https://github.com/basher83/Zammad-MCP/issues)
- [Zammad Documentation](https://docs.zammad.org/)
- [MCP Documentation](https://modelcontextprotocol.io/)

## Trademark Notice

"Zammad" is a trademark of Zammad GmbH. This independent integration is not affiliated with or endorsed by Zammad GmbH or the Zammad Foundation. The name "Zammad" indicates compatibility with the Zammad ticket system.
