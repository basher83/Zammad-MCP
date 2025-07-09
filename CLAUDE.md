# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

```bash
# Setup development environment
./scripts/setup.sh  # macOS/Linux
# or
.\scripts\setup.ps1  # Windows

# Run the MCP server
python -m mcp_zammad
# or with uv
uv run python -m mcp_zammad
# or directly from GitHub
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad

# Run tests
uv run pytest
uv run pytest --cov=mcp_zammad  # with coverage

# Code quality checks
uv run ruff format mcp_zammad tests  # format code
uv run ruff check mcp_zammad tests  # lint
uv run mypy mcp_zammad  # type check

# Security checks
uv run pip-audit  # check for vulnerabilities
uv run bandit -r mcp_zammad  # security analysis
uv run semgrep --config=auto mcp_zammad  # static analysis
uv run safety check  # dependency security check

# Run all quality checks
./scripts/quality-check.sh  # runs all checks above

# Build package
uv build
```

## Development Guidelines

- ALWAYS use 'rg' in place of 'grep'

## Architecture Overview

This is a Model Context Protocol (MCP) server that provides integration with the Zammad ticket system. The codebase follows a clean, modular architecture:

### Core Components

1. **`mcp_zammad/server.py`**: MCP server implementation using FastMCP
   - Implements 16 tools for ticket, user, and organization management (exceeded original plan of 9)
   - Provides 3 resources for direct data access (ticket, user, organization)
   - Includes 3 pre-built prompts for common support scenarios
   - Resources follow URI pattern: `zammad://entity/id`

2. **`mcp_zammad/client.py`**: Zammad API client wrapper
   - Wraps the `zammad_py` library
   - Handles multiple authentication methods (API token, OAuth2, username/password)
   - Provides clean methods for all Zammad operations

3. **`mcp_zammad/models.py`**: Pydantic models for data validation
   - Comprehensive models for all Zammad entities (Ticket, User, Organization, etc.)
   - Request/response models for API operations
   - Ensures type safety throughout the application

### Key Design Patterns

- **Dependency Injection**: The Zammad client is initialized once and shared across all tools
- **Type Safety**: All data is validated using Pydantic models
- **Error Handling**: Consistent error handling with proper MCP error responses
- **Async Support**: Built on async foundations for performance
- **Sentinel Pattern**: Uses `_UNINITIALIZED` sentinel object instead of `None` for better type safety
- **Type Narrowing**: Helper function `get_zammad_client()` ensures proper typing

## Environment Configuration

The server requires Zammad API credentials via environment variables:

```bash
# Required: Zammad instance URL (must include /api/v1)
ZAMMAD_URL=https://your-instance.zammad.com/api/v1

# Authentication (choose one):
ZAMMAD_HTTP_TOKEN=your-api-token  # Recommended
# or
ZAMMAD_OAUTH2_TOKEN=your-oauth2-token
# or
ZAMMAD_USERNAME=your-username
ZAMMAD_PASSWORD=your-password
```

## Testing Strategy

- Unit tests focus on server initialization and tool registration
- Integration tests would require a test Zammad instance
- Use `pytest-asyncio` for async test support
- Coverage reports help identify untested code paths
- **Current Coverage**: 67% (target: 80%+)

### Testing Best Practices

- **Test Organization**: Group fixtures at top, then basic tests, parametrized tests, error cases
- **Mock Strategy**: Always mock `ZammadClient` and external dependencies
- **Factory Fixtures**: Use for flexible test data creation
- **Error Testing**: Always test validation errors and unhappy paths
- **Parametrized Tests**: Use for testing multiple scenarios with same logic

## Code Quality Standards

- **Formatting**: Ruff format with 120-character line length
- **Linting**: Ruff with extensive rule set (see @pyproject.toml)
- **Type Checking**: MyPy with strict settings
- **Python Version**: 3.10+ required

### Modern Python Patterns

- Use Python 3.10+ type syntax: `list[str]` not `List[str]`
- Avoid parameter shadowing: use `article_type` not `type`
- Explicit type casts when needed: `cast(ZammadClient, client)`
- Modern union syntax: `str | None` not `Optional[str]`

## Adding New Features

1. **New Tools**: Add to `server.py` using the `@mcp.tool()` decorator
2. **New Models**: Define in `models.py` using Pydantic
3. **API Methods**: Extend `client.py` with new Zammad operations
4. **Resources**: Add new resource handlers in `server.py`
5. **Prompts**: Define new prompts using `@mcp.prompt()` decorator

## MCP Integration Points

The server exposes:

- **Tools**: Callable functions for Zammad operations
- **Resources**: Direct data access via URIs (e.g., `zammad://ticket/123`)
- **Prompts**: Pre-configured analysis templates

All MCP features follow the Model Context Protocol specification for seamless integration with AI assistants.

## Deployment Options

The server can be run in multiple ways:

1. **Local Installation**: Clone and install with `uv pip install -e .`
2. **Direct from GitHub**: Use `uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad`
3. **PyPI**: `uv pip install mcp-zammad` (when published)

The uvx method is recommended for Claude Desktop integration as it requires no local installation.

### Claude Desktop Integration

For Claude Desktop, configure `.mcp.json`:

```json
{
  "mcpServers": {
    "zammad": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_zammad"]
    }
  }
}
```

The server automatically loads environment variables from the `.env` file in the project directory using `python-dotenv`.

## Known Issues and Limitations

### API Integration (Resolved)

- **Zammad API Expand Behavior**: When using `expand=True` in API calls, Zammad returns string representations of related objects (e.g., `"group": "Users"`) instead of full objects. This has been resolved by updating all Pydantic models to accept both `str` and object types for expanded fields. The following models were updated:
  - **Ticket**: group, state, priority, customer, owner, organization, created_by, updated_by
  - **Article**: created_by, updated_by
  - **User**: organization, created_by, updated_by
  - **Organization**: created_by, updated_by, members

### Performance Issues

- `get_ticket_stats` loads ALL tickets into memory (inefficient for large datasets)
- No caching for frequently accessed data (groups, states, priorities)
- Synchronous client initialization blocks server startup
- No connection pooling for API requests

### Missing Features

- No attachment support for tickets
- No custom field handling
- No bulk operations (e.g., update multiple tickets)
- No webhook/real-time update support
- No time tracking functionality
- Missing `zammad://queue/{group}` resource

### Security Considerations

- No URL validation (potential SSRF vulnerability)
- No input sanitization
- No rate limiting implementation
- No audit logging

## Priority Improvements

1. **Immediate**
   - Fix test collection error in test_server.py (URI parameter mismatch)
   - Increase test coverage to 80%+
   - Fix unused parameters in functions
   - Implement custom exception classes
   - Add proper URL validation

2. **Short Term**
   - Add attachment support
   - Implement caching layer (Redis/memory)
   - Add config file support (in addition to env vars)
   - Optimize `get_ticket_stats` to use pagination

3. **Long Term**
   - Add webhook support for real-time updates
   - Implement bulk operations
   - Add SLA management features
   - Create async version of Zammad client

## Additional Development Tools

The project includes several security and quality tools configured in pyproject.toml:
- **pip-audit**: Checks for known vulnerabilities in dependencies
- **bandit**: Security-focused static analysis
- **semgrep**: Advanced static analysis for security patterns
- **safety**: Dependency vulnerability scanner
- **pre-commit**: Git hooks for code quality enforcement

A convenience script `./scripts/quality-check.sh` runs all quality and security checks in sequence.