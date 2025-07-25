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
uv run safety scan --output json  # dependency security scan

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
   - Implements 18 tools for ticket, user, organization management, and attachments (exceeded original plan of 9)
   - Provides 4 resources for direct data access (ticket, user, organization, queue)
   - Includes 3 pre-built prompts for common support scenarios
   - Resources follow URI pattern: `zammad://entity/id` or `zammad://queue/group`

1. **`mcp_zammad/client.py`**: Zammad API client wrapper
   - Wraps the `zammad_py` library
   - Handles multiple authentication methods (API token, OAuth2, username/password)
   - Provides clean methods for all Zammad operations including attachment support
   - Includes URL validation and input sanitization for security

1. **`mcp_zammad/models.py`**: Pydantic models for data validation
   - Comprehensive models for all Zammad entities (Ticket, User, Organization, Attachment, etc.)
   - Request/response models for API operations
   - Ensures type safety throughout the application
   - Includes HTML sanitization for security

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
- **Current Coverage**: 90.08% (achieved target of 90%!)

### Testing Best Practices

- **Test Organization**: Group fixtures at top, then basic tests, parametrized tests, error cases
- **Mock Strategy**: Always mock `ZammadClient` and external dependencies
- **Factory Fixtures**: Use for flexible test data creation
- **Error Testing**: Always test validation errors and unhappy paths
- **Parametrized Tests**: Use for testing multiple scenarios with same logic
- **Attachment Testing**: Comprehensive test suite covers both client methods and MCP tools
- **Legacy Compatibility**: Tests ensure backward compatibility with existing wrapper functions

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
1. **New Models**: Define in `models.py` using Pydantic
1. **API Methods**: Extend `client.py` with new Zammad operations
1. **Resources**: Add new resource handlers in `server.py`
1. **Prompts**: Define new prompts using `@mcp.prompt()` decorator

## MCP Integration Points

The server exposes:

- **Tools**: Callable functions for Zammad operations
- **Resources**: Direct data access via URIs (e.g., `zammad://ticket/123`)
- **Prompts**: Pre-configured analysis templates

All MCP features follow the Model Context Protocol specification for seamless integration with AI assistants.

## Attachment Support

The server now includes comprehensive attachment support for ticket articles:

### Available Tools

- **`get_article_attachments`**: Lists all attachments for a specific ticket article
  - Returns structured `Attachment` objects with metadata (id, filename, size, content_type, created_at)
  - Usage: `get_article_attachments(ticket_id=123, article_id=456)`

- **`download_attachment`**: Downloads attachment content as base64-encoded data
  - Safe for transmission via MCP protocol
  - Includes error handling for missing or inaccessible attachments
  - Usage: `download_attachment(ticket_id=123, article_id=456, attachment_id=789)`

### Implementation Details

- **Client Methods**: Added `download_attachment()` and `get_article_attachments()` to `ZammadClient`
- **Data Model**: New `Attachment` Pydantic model ensures type safety
- **Base64 Encoding**: Attachment content is automatically encoded for safe transmission
- **Error Handling**: Graceful fallback with descriptive error messages
- **Legacy Support**: Backward-compatible wrapper functions for existing tests

### Security Features

- URL validation prevents SSRF attacks on Zammad instance
- Input sanitization protects against XSS in attachment metadata
- Proper error handling prevents information disclosure

## Deployment Options

The server can be run in multiple ways:

1. **Local Installation**: Clone and install with `uv pip install -e .`
1. **Direct from GitHub**: Use `uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad`
1. **PyPI**: `uv pip install mcp-zammad` (when published)

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

### Performance Issues (Partially Resolved)

- ✅ ~~`get_ticket_stats` loads ALL tickets into memory~~ (Fixed: Now uses pagination for better performance)
- ✅ ~~No caching for frequently accessed data~~ (Fixed: Added caching for groups, states, priorities)
- Synchronous client initialization blocks server startup
- No connection pooling for API requests

### Missing Features

- ✅ ~~No attachment support for tickets~~ (Fixed: Added full attachment support with download and listing capabilities)
- No custom field handling
- No bulk operations (e.g., update multiple tickets)
- No webhook/real-time update support
- No time tracking functionality
- ✅ ~~Missing `zammad://queue/{group}` resource~~ (Fixed: Added queue resource for group-based ticket queues)

### Security Considerations (Partially Resolved)

- ✅ ~~No URL validation~~ (Fixed: Added comprehensive URL validation with SSRF protection)
- ✅ ~~No input sanitization~~ (Fixed: Added HTML sanitization in Pydantic models)
- No rate limiting implementation
- No audit logging

## Priority Improvements

1. **Completed Items** ✅
   - ✅ ~~Increase test coverage to 90%+~~ (Achieved: 90.08%!)
   - ✅ ~~Add proper URL validation~~ (Implemented with SSRF protection)
   - ✅ ~~Add attachment support~~ (Full implementation with download and listing)
   - ✅ ~~Implement caching layer~~ (Added for groups, states, priorities)
   - ✅ ~~Optimize `get_ticket_stats` to use pagination~~ (Improved performance)
   - ✅ ~~Add input sanitization~~ (HTML sanitization in models)

1. **Short Term**
   - Add config file support (in addition to env vars)
   - Implement custom exception classes
   - Add Docker secrets support for additional auth methods

1. **Long Term**
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

## Recent Improvements

### v0.1.3 (Latest) - Major Feature Update

**🎉 New Features:**
- **Attachment Support**: Full implementation of ticket article attachment management
  - `get_article_attachments` tool for listing attachments with metadata
  - `download_attachment` tool for retrieving base64-encoded attachment content
  - New `Attachment` Pydantic model for type safety
  - Comprehensive test coverage (7 additional tests)

**🚀 Performance Improvements:**
- **Optimized Ticket Statistics**: `get_ticket_stats` now uses pagination instead of loading all tickets into memory
- **Caching Layer**: Added intelligent caching for frequently accessed static data (groups, states, priorities)
- **Memory Efficiency**: Reduced memory footprint for large ticket datasets

**🔒 Security Enhancements:**
- **URL Validation**: Comprehensive validation with SSRF attack protection
- **Input Sanitization**: HTML sanitization in Pydantic models prevents XSS attacks
- **Docker Secrets Support**: Enhanced authentication with file-based secrets

**🧪 Quality Assurance:**
- **Test Coverage**: Achieved 90.08% test coverage (exceeded 90% target)
- **Code Quality**: All linting and type checking passes with zero errors
- **Legacy Compatibility**: Backward-compatible wrapper functions ensure no breaking changes

**📚 Documentation:**
- Updated architecture overview with new tool count (18 tools)
- Added comprehensive attachment support documentation
- Enhanced security and performance sections
- Detailed implementation guides for new features

**🔧 Technical Improvements:**
- Improved error handling with graceful fallbacks
- Enhanced type safety throughout the codebase
- Better resource management and cleanup
- Modern Python patterns and best practices