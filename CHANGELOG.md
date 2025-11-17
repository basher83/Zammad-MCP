## [unreleased]

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
- *(config)* Add transport configuration model with env support
- *(main)* Add HTTP transport support via environment config

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
- *(config)* Add port validation and improve error messages
- *(server)* Use proper Request type for health_check endpoint

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
- *(integration)* Improve test helper functions and process management
- *(test)* Replace bare exception handlers with specific types

### 📚 Documentation

- *(server)* Enhance zammad_search_tickets docstring
- *(server)* Enhance tool docstrings with MCP compliance
- Add response format section and update MCP version
- *(changelog)* Update for MCP audit fixes
- *(plan)* Add HTTP transport implementation plan and exclude plans from linting
- *(readme)* Add HTTP transport documentation and update stdio note
- *(deployment)* Add comprehensive HTTP transport deployment guide
- *(env)* Add HTTP transport configuration examples
- *(changelog)* Update for HTTP transport feature
- *(server)* Standardize tool docstrings with Parameters section

### ⚡ Performance

- Optimize code quality and performance

### 🎨 Styling

- *(server)* Move JSONResponse import to top level and add type annotations

### 🧪 Testing

- Add comprehensive tests for add_article tool with params model
- Use specific ValidationError in negative tests
- *(integration)* Add HTTP transport integration tests
- *(integration)* Fix HTTP transport tests per CodeRabbit feedback
- *(integration)* Improve HTTP transport test reliability and coverage

### ⚙️ Miscellaneous Tasks

- *(ai)* Update claude settings
- Fix mypy type checking errors
- Add markdownlint-cli2 integration and reorganize docs
- Update Codacy configuration with improved exclusions
- *(configs)* Update configs
- Remove unused setup script and Codacy-related tasks from configuration
- Update coverage threshold to 86% to match current reality


