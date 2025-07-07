# Changelog

All notable changes to the Zammad MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed

- Simplified escalated ticket count calculation using tuple instead of list
- Updated all development commands to use `uv run` prefix
- Modern Python 3.10+ type annotations throughout

### Security

- Added authentication support for API tokens (recommended)
- Environment variable configuration for credentials

### Known Issues

- `get_ticket_stats` loads all tickets into memory (performance issue)
- No attachment support for tickets
- No URL validation (potential SSRF vulnerability)
- Missing `zammad://queue/{group}` resource
- Test coverage at 67% (target: 80%+)

## [0.1.0] - TBD

### Initial Release

- Initial release
