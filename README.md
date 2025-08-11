# Zammad MCP Server

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/basher83/Zammad-MCP?utm_source=oss&utm_medium=github&utm_campaign=basher83%2FZammad-MCP&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/9cc0ebac926a4d56b0bdf2271d46bbf7)](https://app.codacy.com/gh/basher83/Zammad-MCP/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
![Coverage](https://img.shields.io/badge/coverage-90.08%25-brightgreen)

A Model Context Protocol (MCP) server for Zammad integration, enabling AI assistants to interact with tickets, users, organizations, and more through a standardized interface.

> **Disclaimer**: This project is not affiliated with or endorsed by Zammad GmbH or the Zammad Foundation. This is an independent integration that uses the Zammad API.

## Features

### Tools

- **Ticket Management**
  - `search_tickets` - Search tickets with multiple filters
  - `get_ticket` - Get detailed ticket information with articles (supports pagination)
  - `create_ticket` - Create new tickets
  - `update_ticket` - Update ticket properties
  - `add_article` - Add comments/notes to tickets
  - `add_ticket_tag` / `remove_ticket_tag` - Manage ticket tags

- **Attachment Support** 🆕
  - `get_article_attachments` - List all attachments for a ticket article
  - `download_attachment` - Download attachment content as base64-encoded data

- **User & Organization Management**
  - `get_user` / `search_users` - User information and search
  - `get_organization` / `search_organizations` - Organization data
  - `get_current_user` - Get authenticated user info

- **System Information**
  - `list_groups` - Get all available groups (cached for performance)
  - `list_ticket_states` - Get all ticket states (cached for performance)
  - `list_ticket_priorities` - Get all priority levels (cached for performance)
  - `get_ticket_stats` - Get ticket statistics (optimized with pagination)

### Resources

Direct access to Zammad data:

- `zammad://ticket/{id}` - Individual ticket details
- `zammad://user/{id}` - User profile information
- `zammad://organization/{id}` - Organization details
- `zammad://queue/{group}` - Ticket queue for a specific group 🆕

### Prompts

Pre-configured prompts for common tasks:

- `analyze_ticket` - Comprehensive ticket analysis
- `draft_response` - Generate ticket responses
- `escalation_summary` - Summarize escalated tickets

## Installation

### Option 1: Run Directly with uvx (Recommended)

The quickest way to use the MCP server without installation:

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

For production deployments or when you need more control:

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

Docker images are published with semantic versioning:

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

If you're contributing to the project or need to modify the code:

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

The server requires Zammad API credentials. The recommended approach is to use a `.env` file:

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
   ```

1. The server will automatically load the `.env` file on startup.

**Important**: Never commit your `.env` file to version control. It's already included in `.gitignore`.

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

**Note**: MCP servers communicate via stdio (stdin/stdout), not HTTP. The `-i` flag is required for interactive mode. Port mapping (`-p 8080:8080`) is not needed for MCP operation.

**Important**: The container must run in interactive mode (`-i`) or the MCP server will not receive stdin. Ensure this flag is preserved in any wrapper scripts or shell aliases.

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

## Development

### Setup

For development, you have two options:

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

- API tokens are preferred over username/password
- Tokens must have appropriate permissions for the operations
- Check token expiration in Zammad settings

### Rate Limiting

The server respects Zammad's rate limits. If you encounter rate limit errors:

- Reduce the frequency of requests
- Use pagination for large result sets
- Consider caching frequently accessed data

## Security

Security is a top priority for the Zammad MCP Server. We employ multiple layers of protection and follow industry best practices.

### Reporting Security Issues

**⚠️ IMPORTANT**: Please do NOT create public GitHub issues for security vulnerabilities.

Report security issues via:

- [GitHub Security Advisories](https://github.com/basher83/Zammad-MCP/security/advisories/new) (Preferred)
- See our [Security Policy](SECURITY.md) for detailed reporting guidelines

### Security Features

- ✅ **Input Validation**: All user inputs validated and sanitized ([models.py](mcp_zammad/models.py))
- ✅ **SSRF Protection**: URL validation prevents server-side request forgery ([client.py](mcp_zammad/client.py#L46-L58))
- ✅ **XSS Prevention**: HTML sanitization in all text fields ([models.py](mcp_zammad/models.py#L27-L31))
- ✅ **Secure Authentication**: API tokens preferred over passwords ([client.py](mcp_zammad/client.py#L60-L92))
- ✅ **Dependency Scanning**: Automated vulnerability detection with Dependabot
- ✅ **Security Testing**: Multiple scanners (Bandit, Safety, pip-audit) in CI ([security-scan.yml](.github/workflows/security-scan.yml))

For complete security documentation, see [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING](CONTRIBUTING.md) for detailed guidelines on:

- Development setup
- Code style and quality standards
- Testing requirements
- Pull request process
- GitHub workflows and CI/CD pipeline

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) - see LICENSE file for details

This project uses the same license as the [Zammad project](https://github.com/zammad/zammad) to ensure compatibility and alignment with the upstream project.

## Documentation

- [Architecture](ARCHITECTURE.md) - Technical architecture and design decisions
- [Security](SECURITY.md) - Security policy and vulnerability reporting
- [Contributing](CONTRIBUTING.md) - Development guidelines and contribution process
- [Changelog](CHANGELOG.md) - Version history and changes

## Support

- [GitHub Issues:](https://github.com/basher83/Zammad-MCP/issues)
- [Zammad Documentation:](https://docs.zammad.org/)
- [MCP Documentation:](https://modelcontextprotocol.io/)

## Recent Updates

### Latest Features (v0.1.3)

🎉 **New Attachment Support**: Full implementation for managing ticket article attachments

- List attachments with complete metadata (filename, size, content type)
- Download attachments as base64-encoded content for safe transmission
- Comprehensive error handling and security validation

> **Security Note**: Attachment downloads are base64-encoded for safe transmission via MCP protocol. All attachment metadata is sanitized to prevent XSS attacks. Downloaded content should be validated before processing in client applications.

🚀 **Performance Improvements**:

- Intelligent caching for frequently accessed data (groups, states, priorities)
- Optimized ticket statistics with pagination instead of loading all data into memory
- Reduced memory footprint for large datasets

🔒 **Enhanced Security**:

- URL validation with SSRF attack protection
- HTML sanitization prevents XSS attacks
- Enhanced authentication with Docker secrets support

🧪 **Quality Assurance**: 90.08% test coverage with comprehensive test suite including attachment functionality

See [CLAUDE.md](CLAUDE.md) for complete technical details and implementation notes.

## Trademark Notice

"Zammad" is a trademark of Zammad GmbH. This project is an independent integration and is not affiliated with, endorsed by, or sponsored by Zammad GmbH or the Zammad Foundation. The use of the name "Zammad" is solely to indicate compatibility with the Zammad ticket system.
