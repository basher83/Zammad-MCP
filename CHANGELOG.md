
## [1.1.0] - 2025-12-09


### 🚀 Features

- *(tasks)* Add validation task for Renovate configuration
- Add zammad_create_user tool (#149)

### 🐛 Bug Fixes

- *(docs)* Correct zammad_create_ticket docstring (#148)

### ⚙️ Miscellaneous Tasks

- Remove old instructions
- Remove deprecated agent files

## [1.0.0] - 2025-11-24


### 🚀 Features

- [**breaking**] Add Pydantic request models for MCP tool input validation
- Add zammad-mcp-quality skill for project QA
- Add Conductor workspace configuration (#104)
- *(docs)* Add docstring template helper
- *(server)* Add title annotations to all tools
- *(models)* Add response_format to GetTicketParams
- *(server)* Add markdown formatter for ticket details
- *(server)* Add response format support to zammad_get_ticket
- *(server)* Unify response formats for user and org tools
- Add Streamable HTTP transport support (#119)
- Add attachment upload and delete support (#122)
- *(models)* Add automatic whitespace stripping to input models

### 🐛 Bug Fixes

- Reorganize .gitignore and remove duplicates
- Prevent duplicate kwargs in add_article tool
- Use isoformat() for accurate timezone representation
- Ensure JSON truncation respects limit after adding metadata
- Resolve ticket ID vs number confusion in UX (issue #99)
- Remove markdownlint from Codacy config (requires Docker)
- Resolve Codacy code quality issues
- Resolve ticket resource handler AttributeError with Pydantic models (#103)
- *(config)* Remove unsupported pipeline_remediation section from CodeRabbit config
- *(server)* Change name to 'zammad_mcp' per MCP convention
- *(docs)* Correct docstring template per plan spec
- *(server)* Remove redundant 'Zammad' from Search Tickets title
- *(docs)* Correct zammad_search_tickets docstring accuracy
- *(docs)* Use modern type syntax in docstrings per CLAUDE.md
- *(server)* Handle Article objects in ticket markdown formatter
- *(tests)* Move imports to top level per CLAUDE.md
- *(renovate)* Remove invalid regex slashes from managerFilePatterns
- *(renovate)* Add regex delimiters to managerFilePatterns
- *(renovate)* Use file path syntax instead of sub-preset syntax
- *(changelog)* Add blank line before version headers

### 💼 Other

- *(deps)* Update mcp to 1.21.1 to fix starlette vulnerability

### 🚜 Refactor

- Move article validation to Pydantic models
- Use proper date types for GetTicketStatsParams
- Add strict validation to forbid extra fields
- Rename ArticleCreate.type to article_type to avoid built-in shadow
- Add type annotation to validator info parameter
- Use keyword arguments in get_ticket call
- Use JSON-safe serialization for create_ticket payload
- Use JSON-safe serialization with aliases for add_article
- Use keyword arguments in search_users and search_organizations
- *(server)* Simplify CHARACTER_LIMIT to constant
- *(skills)* Streamline mcp-builder skill content
- *(mise)* Use declarative usage syntax for changelog-bump task

### 📚 Documentation

- *(server)* Enhance zammad_search_tickets docstring
- *(server)* Enhance tool docstrings with MCP compliance
- Add response format section and update MCP version
- *(changelog)* Update for MCP audit fixes
- Add attachment upload/delete feature design
- Add detailed implementation plan for attachment upload/delete
- *(changelog)* Regenerate with all historical versions

### ⚡ Performance

- Optimize code quality and performance

### 🧪 Testing

- Add comprehensive tests for add_article tool with params model
- Use specific ValidationError in negative tests

### ⚙️ Miscellaneous Tasks

- *(ai)* Update claude settings
- Fix mypy type checking errors
- Add markdownlint-cli2 integration and reorganize docs
- Update Codacy configuration with improved exclusions
- *(configs)* Update configs
- Remove unused setup script and Codacy-related tasks from configuration
- Update coverage threshold to 86% to match current reality
- *(config)* Improve cliff.toml format with emojis and better organization
- *(config)* Migrate from markdownlint-cli2 to rumdl
- Update renovate config and add hookify rules
- Release v1.0.0

## [0.2.0] - 2025-10-22


### 🚀 Features

- *(devcontainer)* Add devcontainer configuration and setup script for mise installation
- *(claude)* Introduce agent framework and modernize config
- *(devex)* Add mise tool configuration for development environment
- *(devex)* Automate changelog management with git-cliff
- *(docs)* Add comprehensive migration guide for transitioning from legacy wrappers to ZammadMCPServer
- [**breaking**] Remove legacy wrapper functions (BREAKING CHANGE)
- *(claude)* Add MCP-specialized agent definitions
- *(claude)* Add git branch cleanup command
- *(claude)* Add ultra-think deep analysis command
- *(claude)* Add reusable Claude Code skills
- Implement MCP best practices for LLM agent optimization
- Add pagination metadata and stable sorting to list JSON responses

### 🐛 Bug Fixes

- Update Codacy action reference from commit hash to tag version
- Add correct tag
- *(renovate)* Update renovate configuration to proper format
- *(deps)* Upgrade authlib to 1.6.5 to fix security vulnerabilities
- *(ci)* Configure pip-audit to ignore unfixable pip vulnerability
- *(performance)* Optimize get_ticket_stats to use pagination instead of loading all tickets
- *(security)* Remove PII from initialization logging
- Address CodeRabbit feedback from PR #97
- Address CodeRabbit --prompt-only findings
- Resolve Codacy Static Code Analysis failures

### 💼 Other

- Add repository checks to prevent workflows from running on forks

### 🚜 Refactor

- Address CodeRabbit review feedback
- *(tests)* Add explicit type hints to decorator functions
- *(quality)* Apply CodeRabbit recommendations for code quality
- *(errors)* Add custom AttachmentDownloadError exception
- *(client)* Remove redundant bool() conversion in tag methods
- *(server)* Reduce complexity in zammad_get_ticket_stats method
- *(server)* Use state type IDs for robust state categorization
- *(validation)* Add input validation and fix code quality issues
- Standardize JSON responses with generic 'items' key

### 📚 Documentation

- *(deprecation)* Add Phase 3 execution plan for legacy wrapper removal
- Improve migration guidance and remove duplicate tests
- *(claude)* Enhance git_commit and prime command docs
- *(git-commit)* Add comprehensive analysis of command intent vs implementation
- *(changelog)* Restructure breaking changes per Keep a Changelog format

### 🎨 Styling

- *(ci)* Fix YAML inline comment spacing in codacy workflow

### ⚙️ Miscellaneous Tasks

- Refactor
- Add weekly trigger
- Temp backup coderabbit
- Clarify Safety action pin to v1.0.1 tag target
- *(renovate)* Fix json formatting
- *(claude)* Remove obsolete commands, docs, and hooks
- *(dev)* Pin python version, update mise tasks
- *(dev)* Enhance Claude Code and mise configuration
- *(docs)* Add WARP.md
- *(refactor)* Clean up and apply coderabbit suggestions
- Release v0.2.0

## [0.1.3] - 2025-08-06


### 🚀 Features

- Improve code quality and test coverage to 89.1%
- Implement comprehensive attachment support for ticket articles
- Add zammad://queue/{group} resource for ticket queue management

### 🐛 Bug Fixes

- Pin third-party GitHub Actions to commit SHAs for security
- Address pre-commit hook errors in test files
- Patch ZammadClient in test_initialize_with_envrc_warning to avoid ConfigException
- Add type ignore comments to resolve mypy errors in test_server.py
- Resolve pre-commit hook issues
- Resolve "Zammad client not initialized" error when running with uvx (#39)

### 🚜 Refactor

- Add proper shutdown cleanup to lifespan context manager

### 📚 Documentation

- Add development setup and GitHub MCP server documentation
- Update CHANGELOG for issue #39 fix and recent changes

### 🎨 Styling

- Apply ruff formatting to test files

### 🧪 Testing

- Improve code coverage from 68.72% to 72.88%
- Improve code coverage from 68.72% to 91.7%
- Fix authentication tests to isolate environment variables

### ⚙️ Miscellaneous Tasks

- Configure Renovate to auto-update GitHub Actions SHAs
- Update GitHub Personal Access Token handling and add new MCP commands
- Configure pre-commit hooks to be less strict for test files
- Update configuration files for MCP servers
- Bump version to 0.1.3

## [0.1.2] - 2025-07-24


### 🐛 Bug Fixes

- Update dependencies to resolve starlette security vulnerability

### ⚙️ Miscellaneous Tasks

- Release v0.1.2 - security update

## [0.1.1] - 2025-07-24


### 🚀 Features

- Implement Zammad MCP server with 16 tools and 3 resources
- Add setup scripts for easy installation
- Add .env.example for easy configuration
- Add article pagination to get_ticket
- Add Docker support for containerized deployment

### 🐛 Bug Fixes

- Resolve asyncio conflict in MCP server startup
- Handle Zammad API expand behavior in models
- Remove invalid Renovate configuration options
- *(ci)* Add attestations permission for attest-build-provenance v2
- Remove duplicate log_data initialization
- Resolve failing GitHub workflows
- Add missing permission for Bash(python:*) in settings.local.json
- Handle Docker Hub rate limits in Codacy workflow
- Configure Codacy to use only Python-appropriate tools
- Disable Docker-based tools in Codacy to resolve parsing errors
- Resolve Docker build and authentication issues (#32, #33)
- Revert incorrect CHANGELOG date change

### 🚜 Refactor

- Simplify environment configuration

### 📚 Documentation

- Add comprehensive documentation
- Add CLAUDE.md for AI assistant context
- Update README with uvx support and improved documentation
- Update documentation for recent fixes
- Add Codacy code quality badge to README
- Clean up README structure and improve script execution instructions. Finalizes left over formatting from pr #22

### 🎨 Styling

- Apply ruff formatting to Python files

### ⚙️ Miscellaneous Tasks

- Update .gitignore for comprehensive coverage
- Add development environment configuration
- Configure Renovate for dependency management
- Remove test.md file
- Update dependency lock file
- Clean up .gitignore and add .gitmessage template
- Add .safety-project.ini configuration file for zammad-mcp project
- *(docs)* Remove outdated command documentation and examples
- Remove unused 'serena' server configuration from .mcp.json
- Update permissions in settings.local.json and improve Dockerfile comments
- Release v0.1.1
