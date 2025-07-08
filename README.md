# Zammad MCP Server

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/basher83/Zammad-MCP?utm_source=oss&utm_medium=github&utm_campaign=basher83%2FZammad-MCP&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/9cc0ebac926a4d56b0bdf2271d46bbf7)](https://app.codacy.com/gh/basher83/Zammad-MCP/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)

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

- **User & Organization Management**
  - `get_user` / `search_users` - User information and search
  - `get_organization` / `search_organizations` - Organization data
  - `get_current_user` - Get authenticated user info

- **System Information**
  - `list_groups` - Get all available groups
  - `list_ticket_states` - Get all ticket states
  - `list_ticket_priorities` - Get all priority levels
  - `get_ticket_stats` - Get ticket statistics

### Resources

Direct access to Zammad data:

- `zammad://ticket/{id}` - Individual ticket details
- `zammad://user/{id}` - User profile information
- `zammad://organization/{id}` - Organization details

### Prompts

Pre-configured prompts for common tasks:

- `analyze_ticket` - Comprehensive ticket analysis
- `draft_response` - Generate ticket responses
- `escalation_summary` - Summarize escalated tickets

## Installation

### Prerequisites

Install `uv` - a fast Python package installer and resolver:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install the MCP Server

#### Quick Setup (Recommended)

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
uv pip install -e .

# Or install directly from PyPI (when published)
uv pip install mcp-zammad
```

#### Run Directly from GitHub (No Installation)

You can run the MCP server directly from GitHub using `uvx`:

```bash
# Run directly from GitHub
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad

# Or with environment variables
ZAMMAD_URL=https://your-instance.zammad.com/api/v1 \
ZAMMAD_HTTP_TOKEN=your-api-token \
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad
```

## Configuration

The server requires Zammad API credentials. The recommended approach is to use a `.env` file:

1. Copy the example configuration:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Zammad credentials:

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

3. The server will automatically load the `.env` file on startup.

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
├── pyproject.toml
├── README.md
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
uv run black mcp_zammad

# Lint
uv run ruff check mcp_zammad

# Type checking
uv run mypy mcp_zammad
```

## API Token Generation

To generate an API token in Zammad:

1. Log into your Zammad instance
2. Click on your avatar → Profile
3. Navigate to "Token Access"
4. Click "Create"
5. Name your token (e.g., "MCP Server")
6. Select appropriate permissions
7. Copy the generated token

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Development setup
- Code style and quality standards
- Testing requirements
- Pull request process

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) - see LICENSE file for details

This project uses the same license as the [Zammad project](https://github.com/zammad/zammad) to ensure compatibility and alignment with the upstream project.

## Documentation

- [Architecture](ARCHITECTURE.md) - Technical architecture and design decisions
- [Contributing](CONTRIBUTING.md) - Development guidelines and contribution process
- [Changelog](CHANGELOG.md) - Version history and changes

## Support

- GitHub Issues: [Report bugs or request features]
- Zammad Documentation: <https://docs.zammad.org/>
- MCP Documentation: <https://modelcontextprotocol.io/>

## Trademark Notice

"Zammad" is a trademark of Zammad GmbH. This project is an independent integration and is not affiliated with, endorsed by, or sponsored by Zammad GmbH or the Zammad Foundation. The use of the name "Zammad" is solely to indicate compatibility with the Zammad ticket system.
