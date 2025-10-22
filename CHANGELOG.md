# Changelog

All notable changes to the Zammad MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-10-22

### Added

- **devcontainer**: Add devcontainer configuration and setup script for mise installation
- **claude**: Introduce agent framework and modernize config
- **devex**: Add mise tool configuration for development environment
- **devex**: Automate changelog management with git-cliff
- **docs**: Add comprehensive migration guide for transitioning from legacy wrappers to ZammadMCPServer
- [**breaking**] Remove legacy wrapper functions (BREAKING CHANGE)
- **claude**: Add MCP-specialized agent definitions
- **claude**: Add git branch cleanup command
- **claude**: Add ultra-think deep analysis command
- **claude**: Add reusable Claude Code skills
- Implement MCP best practices for LLM agent optimization
- Add pagination metadata and stable sorting to list JSON responses

### Dependencies

- **deps**: Update python:3.13-slim Docker digest to 6f79e7a
- **deps**: Update github/codeql-action digest to 76621b6 (v3) (#44)
- **deps**: Update actions/checkout digest to 08eba0b (v4) (#46)
- **deps**: Update actions/checkout digest to 08c6903 (v4)
- **deps**: Update github/codeql-action digest to df55935 (v3) (#52)
- **deps**: Update pyupio/safety-action digest to c14ed93 () (#53)
- **deps**: Update python:3.13-slim Docker digest to 4555eb8
- **deps**: Update astral-sh/setup-uv digest to d9e0f98 (v6.4.3)
- **deps**: Pin codacy/codacy-analysis-cli-action digest to 562ee3e (v4.4.7)
- **deps**: Update python:3.13-slim Docker digest to 2a928e1
- **deps**: Update python:3.13-slim Docker digest to 4d55aff
- **deps**: Update github/codeql-action digest to 96f518a (v3) (#58)
- **deps**: Update astral-sh/setup-uv digest to 4959332 (v6.5.0)
- **deps**: Update python:3.13-slim Docker digest to 27f90d7
- **deps**: Update github/codeql-action digest to 3c3833e (v3) (#62)
- **deps**: Update actions/attest-build-provenance digest to 977bb37 (v2)
- **deps**: Update astral-sh/setup-uv digest to 557e51d (v6.6.0)
- **deps**: Update actions/setup-python digest to e797f83 (v5.6.0)
- **deps**: Update github/codeql-action digest to f1f6e5f (v3) (#68)
- **deps**: Update python:3.13-slim Docker digest to 1bca020
- **deps**: Update github/codeql-action digest to 192325c (v3) (#71)
- **deps**: Update astral-sh/setup-uv digest to b75a909 (v6.6.1)
- **deps**: Update python:3.13-slim Docker digest to 58c30f5
- **deps**: Update github/codeql-action digest to 3599b3b (v3) (#74)
- **deps**: Update docker/login-action digest to 5e57cd1 (v3) (#75)
- **deps**: Update python:3.13-slim Docker digest to 5f55cdf
- **deps**: Update astral-sh/setup-uv digest to d0cc045 (v6.7.0)
- **deps**: Update docker/login-action digest to 5e57cd1 (v3.5.0)
- **deps**: Update github/codeql-action digest to a8d1ac4 (v3) (#80)
- **deps**: Update python:3.13-slim Docker digest to 087a9f3
- **deps**: Update github/codeql-action digest to f443b60 (v3)
- **deps**: Update astral-sh/setup-uv digest to 3259c62 (v6.8.0)
- **renovate**: Fix json formatting
- **deps**: Update github/codeql-action digest to 16140ae (v4) (#89)
- **deps**: Update python:3.13-slim Docker digest to 0796012
- **deps**: Update dependency uv to v0.9.4
- **deps**: Update astral-sh/setup-uv digest to 2ddd2b9 (v7.1.0)

### Documentation

- **deprecation**: Add Phase 3 execution plan for legacy wrapper removal
- Improve migration guidance and remove duplicate tests
- **claude**: Enhance git_commit and prime command docs
- **git-commit**: Add comprehensive analysis of command intent vs implementation
- **changelog**: Restructure breaking changes per Keep a Changelog format

### Fixed

- Update Codacy action reference from commit hash to tag version
- Add correct tag
- **renovate**: Update renovate configuration to proper format
- **deps**: Upgrade authlib to 1.6.5 to fix security vulnerabilities
- **ci**: Configure pip-audit to ignore unfixable pip vulnerability
- **performance**: Optimize get_ticket_stats to use pagination instead of loading all tickets
- **security**: Remove PII from initialization logging
- Address CodeRabbit feedback from PR #97
- Address CodeRabbit --prompt-only findings
- Resolve Codacy Static Code Analysis failures

### Miscellaneous Tasks

- Refactor
- Add weekly trigger
- Temp backup coderabbit
- Clarify Safety action pin to v1.0.1 tag target
- **claude**: Remove obsolete commands, docs, and hooks
- **dev**: Pin python version, update mise tasks
- **dev**: Enhance Claude Code and mise configuration
- **docs**: Add WARP.md
- **refactor**: Clean up and apply coderabbit suggestions

### Refactor

- Address CodeRabbit review feedback
- **tests**: Add explicit type hints to decorator functions
- **quality**: Apply CodeRabbit recommendations for code quality
- **errors**: Add custom AttachmentDownloadError exception
- **client**: Remove redundant bool() conversion in tag methods
- **server**: Reduce complexity in zammad_get_ticket_stats method
- **server**: Use state type IDs for robust state categorization
- **validation**: Add input validation and fix code quality issues
- Standardize JSON responses with generic 'items' key

### Styling

- **ci**: Fix YAML inline comment spacing in codacy workflow

## [0.1.3] - 2025-08-06

### Added

- Improve code quality and test coverage to 89.1%
- Implement comprehensive attachment support for ticket articles
- Add zammad://queue/{group} resource for ticket queue management

### Dependencies

- **deps**: Update python digest to (3.12)
- **deps**: Update python:3.13-slim Docker digest to 4c2cf99
- **deps**: Pin dependencies
- **deps**: Update docker/login-action digest to 184bdaa (v3) (#41)
- **deps**: Update docker/metadata-action digest to c1e5197 (v5.7.0)
- **deps**: Update docker/login-action digest to 184bdaa (v3.4.0)

### Documentation

- Add development setup and GitHub MCP server documentation
- Update CHANGELOG for issue #39 fix and recent changes

### Fixed

- Pin third-party GitHub Actions to commit SHAs for security
- Address pre-commit hook errors in test files
- Patch ZammadClient in test_initialize_with_envrc_warning to avoid ConfigException
- Add type ignore comments to resolve mypy errors in test_server.py
- Resolve pre-commit hook issues
- Resolve "Zammad client not initialized" error when running with uvx (#39)

### Miscellaneous Tasks

- Configure Renovate to auto-update GitHub Actions SHAs
- Update GitHub Personal Access Token handling and add new MCP commands
- Configure pre-commit hooks to be less strict for test files
- Update configuration files for MCP servers
- Bump version to 0.1.3

### Refactor

- Add proper shutdown cleanup to lifespan context manager

### Styling

- Apply ruff formatting to test files

### Testing

- Improve code coverage from 68.72% to 72.88%
- Improve code coverage from 68.72% to 91.7%
- Fix authentication tests to isolate environment variables

## [0.1.2] - 2025-07-24

### Fixed

- Update dependencies to resolve starlette security vulnerability

### Miscellaneous Tasks

- Release v0.1.2 - security update

## [0.1.1] - 2025-07-24

### Added

- Implement Zammad MCP server with 16 tools and 3 resources
- Add setup scripts for easy installation
- Add .env.example for easy configuration
- Add article pagination to get_ticket
- Add Docker support for containerized deployment

### Dependencies

- **deps**: Update astral-sh/setup-uv action to v6
- **deps**: Update python Docker tag to v3.13
- **deps**: Migrate config renovate.json
- **deps**: Update dependency python
- **deps**: Update actions/attest-build-provenance action to v2
- **deps**: Update docker/build-push-action action to v6
- **deps**: Update codacy/codacy-analysis-cli-action digest to 0991600
- **deps**: Update astral-sh/setup-uv action to v6.4.1
- **deps**: Update codacy/codacy-analysis-cli-action digest to d28ce58
- **deps**: Update astral-sh/setup-uv action to v6.4.3

### Documentation

- Add comprehensive documentation
- Add CLAUDE.md for AI assistant context
- Update README with uvx support and improved documentation
- Update documentation for recent fixes
- Add Codacy code quality badge to README
- Clean up README structure and improve script execution instructions. Finalizes left over formatting from pr #22

### Fixed

- Resolve asyncio conflict in MCP server startup
- Handle Zammad API expand behavior in models
- Remove invalid Renovate configuration options
- **ci**: Add attestations permission for attest-build-provenance v2
- Remove duplicate log_data initialization
- Resolve failing GitHub workflows
- Add missing permission for Bash(python:*) in settings.local.json
- Handle Docker Hub rate limits in Codacy workflow
- Configure Codacy to use only Python-appropriate tools
- Disable Docker-based tools in Codacy to resolve parsing errors
- Resolve Docker build and authentication issues (#32, #33)
- Revert incorrect CHANGELOG date change

### Miscellaneous Tasks

- Update .gitignore for comprehensive coverage
- Add development environment configuration
- Configure Renovate for dependency management
- Remove test.md file
- Update dependency lock file
- Clean up .gitignore and add .gitmessage template
- Add .safety-project.ini configuration file for zammad-mcp project
- **docs**: Remove outdated command documentation and examples
- Remove unused 'serena' server configuration from .mcp.json
- Update permissions in settings.local.json and improve Dockerfile comments
- Release v0.1.1

### Refactor

- Simplify environment configuration

### Styling

- Apply ruff formatting to Python files

<!-- generated by git-cliff -->
