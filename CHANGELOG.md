# Changelog

All notable changes to the Zammad MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2025-08-06

### Fixed

- Fixed "Zammad client not initialized" error when running with uvx (#39)
  - Moved lifespan configuration to FastMCP constructor for proper initialization
  - Ensures client initialization regardless of how the server is started

### Added

- Added proper shutdown cleanup to lifespan context manager
  - Client reference is now properly cleaned up on server shutdown
  - Added logging for cleanup visibility

### Security

- Pinned all third-party GitHub Actions to commit SHAs to prevent supply chain attacks
- Configured Renovate to automatically update pinned GitHub Actions SHAs

### Changed

- Improved test coverage from 68.72% to 92.65%
- Added comprehensive tests for all MCP tools including:
  - `update_ticket`, `get_organization`, `search_organizations`
  - `list_groups`, `list_ticket_states`, `list_ticket_priorities`
  - `get_current_user`, `search_users`, `get_ticket_stats`
- Added tests for client methods to improve coverage
- Added legacy wrapper functions in server.py for test compatibility

### Documentation

- Added development setup guide with Tailscale configuration for Codespaces
- Added comprehensive GitHub MCP server documentation with Docker and Claude Code setup instructions

## [0.1.2] - 2025-07-24

### Security

- Updated starlette from 0.47.1 to 0.47.2 to fix CVE-2025-54121 (low impact vulnerability in multipart form handling)
- Updated mcp from 1.10.1 to 1.12.2

## [0.1.1] - 2025-07-24

### Fixed

- Fixed Docker image build to properly install the mcp-zammad package (#32)
- Improved error message when ZAMMAD_TOKEN is used instead of ZAMMAD_HTTP_TOKEN (#33)
- Added client configuration tests for better coverage

### Changed

- Simplified deployment by removing Docker Compose in favor of direct `docker run` and `uvx` commands
- Prioritized `uvx` as the recommended installation method for simplicity
- Updated Docker documentation to focus on `docker run` with clear examples for environment variables and secrets
- Removed `docker-compose.yml`, `docker-compose.override.yml`, and `docker-compose.dev.yml` as they added unnecessary complexity for MCP servers

## [0.1.0] - 2025-07-11

### Added

- Initial implementation of Zammad MCP Server
- 16 tools for ticket, user, and organization management
- 3 resources for direct data access (ticket, user, organization)
- 3 pre-built prompts for common support scenarios
- Support for multiple authentication methods (API token, OAuth2, username/password)
- Comprehensive Pydantic models for type safety
- Setup scripts for Windows and Unix systems
- Support for running via `uvx` directly from GitHub
- Sentinel pattern for better type safety with `_UNINITIALIZED`
- Documentation for GitHub Actions security secrets configuration
- Comprehensive GitHub workflows documentation in CONTRIBUTING.md
- Docker image published to GitHub Container Registry (ghcr.io)
- Comprehensive security scanning pipeline (bandit, semgrep, pip-audit)
- Pre-commit hooks for code quality enforcement

### Changed

- Simplified escalated ticket count calculation using tuple instead of list
- Updated all development commands to use `uv run` prefix
- Modern Python 3.10+ type annotations throughout
- Switched from manual Safety CLI execution to official pyupio/safety-action in GitHub workflows
- Removed duplicate Codacy Trivy scan from security-scan.yml (already covered by dedicated Codacy workflow)

### Fixed

- Fixed MCP server startup issue where `asyncio.run()` was called within an already running event loop
- Fixed Pydantic validation errors when Zammad API returns string representations for expanded fields instead of objects
- Added support for both string and object types in all model expanded fields:
  - Ticket model: group, state, priority, customer, owner, organization, created_by, updated_by
  - Article model: created_by, updated_by
  - User model: organization, created_by, updated_by
  - Organization model: created_by, updated_by, members
- Fixed `get_ticket_stats` implementation to handle both string and object state formats
- Simplified environment configuration to use `.env` files with `python-dotenv` for better Claude Desktop compatibility
- Added `article_limit` and `article_offset` parameters to `get_ticket` to prevent token limit errors on tickets with many articles
- Fixed documentation inconsistency: all ZAMMAD_URL examples now correctly include `/api/v1` suffix

### Security

- Added authentication support for API tokens (recommended)
- Environment variable configuration for credentials
- Integrated multiple security scanning tools in CI/CD pipeline
- Pre-commit hooks for security checks

### Known Issues

- `get_ticket_stats` loads all tickets into memory (performance issue)
- No attachment support for tickets
- No URL validation (potential SSRF vulnerability)
- Missing `zammad://queue/{group}` resource
- Test coverage at 91.7% (exceeded target of 80%+)
