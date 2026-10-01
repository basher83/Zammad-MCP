# Zammad MCP Server

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/basher83/Zammad-MCP?utm_source=oss&utm_medium=github&utm_campaign=basher83%2FZammad-MCP&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/9cc0ebac926a4d56b0bdf2271d46bbf7)](https://app.codacy.com/gh/basher83/Zammad-MCP/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![Coverage](https://app.codacy.com/project/badge/Coverage/9cc0ebac926a4d56b0bdf2271d46bbf7)](https://app.codacy.com/gh/basher83/Zammad-MCP/dashboard)

An MCP server that connects AI assistants to Zammad, providing tools for managing tickets, users, organizations, attachments, and knowledge base content.

> **Disclaimer**: This project is not affiliated with or endorsed by Zammad GmbH or the Zammad Foundation. This is an independent integration that uses the Zammad API.

## Features

### Tools

- **Ticket Management**
  - `zammad_search_tickets` - Search tickets with multiple filters
  - `zammad_get_ticket` - Get detailed ticket information with articles (supports pagination); custom object attributes are included
  - `zammad_create_ticket` - Create new tickets
  - `zammad_update_ticket` - Update ticket properties, including custom object attributes via `custom_fields`
  - `zammad_add_article` - Add comments/notes to tickets
  - `zammad_merge_tickets` - Merge a ticket into another (irreversible)
  - `zammad_add_ticket_tag` / `zammad_remove_ticket_tag` - Manage ticket tags
  - `zammad_bulk_update_tickets` - Update, assign, tag, or close up to 100 tickets in one call with per-ticket failure reporting
  - `zammad_get_ticket_tags` - Get tags assigned to a specific ticket
  - `zammad_list_tags` - List all tags defined in the system (requires admin.tag permission)
  - `zammad_export_tickets` - Export tickets with their conversation articles to a JSONL file on the server host (requires `ZAMMAD_EXPORT_DIR`; see [Ticket Export](#ticket-export-optional))

- **Attachment Support**
  - `zammad_get_article_attachments` - List attachments for a ticket article
  - `zammad_download_attachment` - Download attachment content (base64-encoded)

- **User & Organization Management**
  - `zammad_create_user` - Create a Zammad user
  - `zammad_get_user` / `zammad_search_users` - User information and search
  - `zammad_get_organization` / `zammad_search_organizations` - Organization data
  - `zammad_get_current_user` - Get authenticated user info

- **System Information**
  - `zammad_list_groups` - Get all available groups (cached for performance)
  - `zammad_list_ticket_states` - Get all ticket states (cached for performance)
  - `zammad_list_ticket_priorities` - Get all priority levels (cached for performance)
  - `zammad_get_ticket_stats` - Get ticket statistics (optimized with pagination)

- **Webhook Events** (HTTP transport only)
  - `zammad_list_events` - Poll ticket events delivered by Zammad webhooks (see [Webhook Events](#webhook-events-http-transport-only))

- **Knowledge Base** (read-only, requires `knowledge_base.reader` or `knowledge_base.editor` permission)
  - `zammad_list_knowledge_bases` - List all knowledge bases
  - `zammad_get_knowledge_base` - Get details of one knowledge base by ID
  - `zammad_get_kb_category` - Get a knowledge base category by ID
  - `zammad_list_kb_answers` - List answers in a knowledge base category
  - `zammad_search_kb_answers` - Case-insensitive substring search of answer titles and bodies
  - `zammad_get_kb_answer` - Get an answer by ID with its resolved title and body

### Resources

Access Zammad data directly:

- `zammad://ticket/{id}` - Individual ticket details
- `zammad://user/{id}` - User profile information
- `zammad://organization/{id}` - Organization details
- `zammad://queue/{group}` - Ticket queue for a group
- `zammad://kb/{kb_id}` - Knowledge base details
- `zammad://kb/{kb_id}/category/{category_id}` - Knowledge base category
- `zammad://kb/{kb_id}/answer/{answer_id}` - Knowledge base answer with title and body

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

# If you must skip TLS verification (self-signed / internal CA), add:
#   -e ZAMMAD_INSECURE=true

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

- `latest` - Latest successful build from the default branch; may be unstable
- `1.2.3` - Specific version (recommended for production)
- `1.2` - Latest patch of 1.2 minor release
- `1` - Latest minor/patch of 1.x major release
- `main` - Latest main branch (may be unstable)

```bash
# Recommended for production - pin to specific version
docker pull ghcr.io/basher83/zammad-mcp:1.2.0
```

View all versions on [GitHub Container Registry](https://github.com/basher83/Zammad-MCP/pkgs/container/zammad-mcp).

### Option 3: For Developers

To contribute or modify the code, install [mise](https://mise.jdx.dev/getting-started.html). `mise.toml` pins the Python and uv versions and defines the project tasks.

```bash
# Clone the repository
git clone https://github.com/basher83/zammad-mcp.git
cd zammad-mcp

# Install the pinned tools from mise.toml (Python, uv, prek, git-cliff, and others)
mise install

# Install the Python dependencies into .venv (uv sync)
mise run setup

# Install the pre-commit hooks
mise run hooks-install
```

If mise asks you to trust the repository configuration, run `mise trust`. The [Development](#development) section below links the contributor guides.

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

   # Optional: Disable TLS certificate verification (NOT recommended for production)
   # Truthy values only: 1, true, yes, on. Unset (default) keeps TLS verification enabled.
   # ZAMMAD_INSECURE=true

   # Optional: Logging level (default: INFO)
   # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
   # LOG_LEVEL=INFO
   ```

1. The server will automatically load the `.env` file on startup.

`.env.example` lists every optional variable with a comment. The
[configuration reference](docs/reference/configuration.md) documents each variable with its default and allowed values.
The optional features are summarized below.

### Transport Configuration (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | Transport type: `stdio` or `http` |
| `MCP_HOST` | `127.0.0.1` | Host address for HTTP transport |
| `MCP_PORT` | - | Port number for HTTP transport (required if `MCP_TRANSPORT=http`) |

### Audit Logging (Optional)

Audit logging is disabled by default. When `ZAMMAD_AUDIT_LOG_ENABLED` is set, the server writes one JSON Lines record
per tool call, connection attempt, and URL security check to `stderr`, a file, or syslog, with secrets redacted.
See [Audit logging](docs/reference/configuration.md#audit-logging) for the variables and the record format.

### Ticket Export (Optional)

`zammad_export_tickets` writes a JSON Lines file on the host that runs the MCP server. It is disabled until
`ZAMMAD_EXPORT_DIR` names an existing directory, and every output path must resolve inside that directory.
See [Ticket export](docs/reference/configuration.md#ticket-export) for the variables, filters, and confinement rules.

**Important**: Keep your `.env` file out of version control (already in `.gitignore`).

## Response Formats

Tools that return Markdown by default accept a `response_format` parameter with two values:

- **Markdown** (default): Human-readable format optimized for LLM consumption
- **JSON**: Machine-readable format with complete metadata

These are the search, get, and list tools for tickets, users, organizations, groups, states, priorities, tags, and
knowledge base content. The write tools, `zammad_get_article_attachments`, `zammad_download_attachment`,
`zammad_get_current_user`, `zammad_get_ticket_stats`, `zammad_export_tickets`, and `zammad_list_events` return
structured results and have no `response_format` parameter.

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
      "command": "mcp-zammad",
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
# Run the server from a repository checkout
uv run mcp-zammad

# Or with environment variables
ZAMMAD_URL=https://instance.zammad.com/api/v1 ZAMMAD_HTTP_TOKEN=token uv run mcp-zammad
```

### HTTP Transport (Remote/Cloud Deployment)

The server supports Streamable HTTP transport for remote deployments. Set `MCP_TRANSPORT=http` and `MCP_PORT`.
`MCP_HOST` defaults to `127.0.0.1`. The MCP endpoint is `/mcp` on that host and port.

⚠️ **SECURITY WARNING**: The server does not implement inbound MCP client authentication. `ZAMMAD_*` credentials
authenticate the server to Zammad, not MCP clients. Bind to `0.0.0.0` only behind an authenticated TLS proxy or inside
a network restricted to trusted clients.

The [HTTP Transport Deployment Guide](docs/deployment/http-transport.md) covers running with Docker, reverse proxy,
systemd, Docker Compose, cloud platforms, client configuration, and security.

### Webhook Events (HTTP Transport Only)

Zammad can push ticket events to `POST /webhooks/zammad`, and MCP clients poll them with `zammad_list_events`.
This needs `MCP_TRANSPORT=http` and `ZAMMAD_WEBHOOK_SECRET`. Retention is in memory, bounded to 1000 events, and
lost on restart. See [Webhook events](docs/deployment/http-transport.md#webhook-events) for the Zammad setup,
the status codes, and the polling procedure.

## Examples

### Search for Open Tickets

```text
Use zammad_search_tickets with state="open" to find all open tickets
```

### Create a Support Ticket

```text
Use zammad_create_ticket with:
- title: "Customer needs help with login"
- group: "Support"
- customer: "customer@example.com"
- article_body: "Customer reported unable to login..."
```

### Update and Respond to a Ticket

```text
1. Use zammad_get_ticket with ticket_id=123 to see the full conversation
2. Use zammad_add_article to add your response
3. Use zammad_update_ticket to change state to "pending reminder" with a pending_time (e.g. "2026-07-01T08:00:00Z")
```

### Analyze Escalated Tickets

```text
Use the escalation_summary prompt to get a report of all tickets approaching escalation
```

### Upload Attachments to a Ticket

```text
Use zammad_add_article with attachments parameter:
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

### Merge Duplicate Tickets

Useful for collapsing recurring auto-generated tickets (cron failures, monitoring noise) into one incident. The source ticket's articles move to the target and the source is closed as "merged". This cannot be undone.

```text
Use zammad_merge_tickets with:
- source_ticket_id: 123          # internal ID of the ticket to merge away
- target_ticket_number: "20002"  # display number of the surviving ticket
```

`target_ticket_id` may be given instead of `target_ticket_number`, but not both.

## Development

[CONTRIBUTING.md](CONTRIBUTING.md) covers the development setup, the test commands, the quality gates, and the
release process. [ARCHITECTURE.md](ARCHITECTURE.md) has the module map, the component boundaries, and the design
constraints.

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
- For self-signed/internal certs only: set `ZAMMAD_INSECURE=true` to bypass TLS verification

### Authentication Errors

- Use API tokens over username/password
- Ensure tokens have permissions for the operations
- Check token expiration in Zammad settings

### Rate Limiting

The client retries safe reads, can throttle requests, and opens a circuit breaker after repeated failures.
When retries are exhausted or the circuit is open, tools return an `Error:` message that names the cause. A 429
outcome points at rate limiting and `ZAMMAD_RATE_LIMIT_ENABLED`. Reduce request frequency, paginate, or enable
throttling if you keep hitting Zammad's limits. See
[Rate limiting, retries, and circuit breaker](docs/reference/configuration.md#rate-limiting-retries-and-circuit-breaker)
for the variables and the retry rules.

## Security

The server implements multiple layers of protection following industry best practices.

### Reporting Security Issues

**⚠️ IMPORTANT**: Do not create public GitHub issues for security vulnerabilities.

Report via [GitHub Security Advisories](https://github.com/basher83/Zammad-MCP/security/advisories/new) (preferred) or see [SECURITY.md](SECURITY.md).

### Security Features

- ✅ **Request Validation**: Strict request models reject unknown fields and validate constrained inputs ([models.py](mcp_zammad/models.py))
- ⚠️ **URL Validation**: Rejects malformed and non-HTTP(S) URLs, but does not block private-network targets ([client.py](mcp_zammad/client.py))
- ✅ **HTML Sanitization**: Sanitizes selected HTML-bearing fields ([models.py](mcp_zammad/models.py))
- ✅ **Upstream Authentication**: Supports API tokens, OAuth2, and username/password for Zammad ([client.py](mcp_zammad/client.py))
- ✅ **Audit Logging**: Opt-in JSON Lines records for tool calls, connection outcomes, and URL checks with secret redaction ([audit.py](mcp_zammad/audit.py))
- ✅ **Dependency Scanning**: CI runs pip-audit; Dependabot security alerts are enabled separately in GitHub
- ✅ **Security Testing**: CI runs Bandit and pip-audit ([security-scan.yml](.github/workflows/security-scan.yml))

See [SECURITY.md](SECURITY.md) for complete documentation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code standards, testing, and pull request guidelines.

## License

[AGPL-3.0-or-later](LICENSE) — matches the [Zammad project](https://github.com/zammad/zammad) license.

## Documentation

- [Documentation index](docs/README.md) — Index of all documentation
- [HTTP Transport Deployment Guide](docs/deployment/http-transport.md) — Reverse proxy, systemd, Compose, cloud deployment, and webhook events
- [Configuration reference](docs/reference/configuration.md) — Every environment variable with its default and allowed values
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
