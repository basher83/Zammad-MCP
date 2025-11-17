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
- Add Streamable HTTP transport support (#119)
- *(models)* Add AttachmentUpload model with security validation
- *(models)* Add attachments support to ArticleCreate
- *(models)* Add DeleteAttachmentParams model
- *(client)* Add attachment support to add_article method
- *(client)* Add delete_attachment method
- *(server)* Add AttachmentDeletionError exception
- *(server)* Add attachment support to zammad_add_article tool
- *(server)* Add zammad_delete_attachment tool

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
- Add type ignore for requests import to satisfy mypy

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

### 📚 Documentation

- *(server)* Enhance zammad_search_tickets docstring
- *(server)* Enhance tool docstrings with MCP compliance
- Add response format section and update MCP version
- *(changelog)* Update for MCP audit fixes
- Add attachment upload/delete feature design
- Add detailed implementation plan for attachment upload/delete

### ⚡ Performance

- Optimize code quality and performance

### 🧪 Testing

- Add comprehensive tests for add_article tool with params model
- Use specific ValidationError in negative tests
- Add missing server-layer tests and fix code quality issues

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

