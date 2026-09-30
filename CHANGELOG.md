
## [unreleased]


### 🚀 Features

- Add tag listing and retrieval tools (#174)
- *(time-accounting)* Add `time_unit` support to `update_ticket` and `add_article` (#211)
- *(deps)* Migrate from bundled FastMCP 1 to standalone FastMCP 3
- *(triage)* Add repo triage skills
- *(audit)* Add opt-in JSON Lines audit logging for security events
- *(export)* Add bulk ticket export to JSONL
- *(kb)* Add read-only Knowledge Base support
- *(search)* Add creation date range filters to ticket search
- Add `pending_time` to `update_ticket` for pending states
- *(models)* Accept case-insensitive constant inputs
- *(tickets)* Add `zammad_bulk_update_tickets` tool
- *(tickets)* Support custom Zammad object attributes on read and update
- *(webhooks)* Receive Zammad webhook events and expose `zammad_list_events`
- *(models)* Add ticket merge request and result models
- *(client)* Wrap the legacy Zammad `ticket_merge` endpoint
- *(server)* Add `zammad_merge_tickets` destructive tool
- *(client)* Add rate limiting, retries, and circuit breaker for Zammad requests

### 🐛 Bug Fixes

- Address CodeRabbit review feedback
- Resolve Codacy D-series docstring violations in changed files
- *(tests)* Add local fake Zammad server to HTTP integration fixture
- *(tests)* Rename format param to fmt to avoid shadowing builtin (Ruff A002)
- *(tests)* Fully teardown mock Zammad server in fixture
- *(triage)* Address review feedback
- *(triage)* Tighten review follow-ups
- *(triage)* Remove unused workflow context fetches
- *(deps)* Override protobuf to >=5.29.6 to resolve GHSA-8r5m-rr7v-pfvq
- *(deps)* Isolate semgrep from uv dev graph
- *(codex)* Address plugin review blockers
- *(codacy)* Ignore plugin bundle in static analysis
- *(deps)* Remediate dependency alerts
- *(deps)* Clear dependency audit commit blocker
- *(audit)* Load .env before building audit logger
- *(kb)* Address Codacy pydocstyle and ruff findings
- *(kb)* Address CodeRabbit review findings
- *(kb)* Address remaining Codacy pydocstyle minor findings
- Align docstring formatting with Codacy D203/D212/D213 rules
- *(kb)* Address PR review — use init bootstrap, typed shape errors, mypy clean
- *(kb)* Fall back to any legacy translation body when ids are stale
- *(export)* Annotate `zammad_export_tickets` as a write tool
- Address review findings on export paging, syslog, host checks, redaction
- *(deps)* Remediate audit failures and remove vulnerable Safety tooling
- Expose flat MCP tool arguments
- Resolve audited dependency vulnerabilities
- Preserve dependency requirements during audit updates
- Align module docstrings with Codacy
- Satisfy Codacy docstring rules
- *(prompts)* Accept string arguments for `ticket_id`
- Don't HTML-escape quotes/apostrophes in plain-text article/ticket content
- Preserve quotes when updating ticket titles
- *(stats)* Categorize by `state_type_id` (seeded and stable), not state name
- *(client)* Request expand=true when fetching a single ticket
- *(client)* Build `get_ticket` URL from `zammad_py`'s normalised base
- *(stats)* Flag group-filtered counts truncated at the search cap
- [**breaking**] Remove `zammad_delete_attachment`, Zammad has no such endpoint
- Add customer field to `zammad_update_ticket`
- Address CodeRabbit review on `zammad_update_ticket`
- *(search)* Show date bounds in search results header
- Surface article attachments when reading tickets
- Sanitize attachment metadata in ticket markdown
- Sanitize `article_id` in attachments header too
- *(models)* Keep quotes in update-ticket titles and bound the expanded GET
- *(tickets)* Bound bulk tag names like the single-tag tools
- *(events)* Return oldest page first so `next_since` cursor never skips events
- *(client)* Percent-encode the merge target number path segment
- *(server)* Give accurate guidance for 5xx exhaustion and throttled writes
- *(tools)* Expose flat arguments for merge, bulk update, and list events
- Address review findings on resilience, webhooks, events and CI aggregate
- *(deps)* Cap fastmcp <4 and mcp <2 in project dependencies

### 💼 Other

- Address PR review feedback (#213)
- Constrain mcp and fastmcp below their next majors
- Declare requests as a direct dependency with type stubs
- Relock for the requests and types-requests declarations

### 🚜 Refactor

- *(export)* Split `zammad_export_tickets` into focused helpers
- *(client)* Build ticket search clauses declaratively
- *(client)* Pick the legacy translation body from one candidate list
- Drop orphaned `_destructive_write_annotations` and harden guard test
- Split attachment formatting to cut cyclomatic complexity
- *(client)* Build search clauses and update payloads declaratively
- *(webhooks)* Address Codacy static analysis findings

### 📚 Documentation

- *(skills)* Add Zammad documentation guidance
- Add maintainer pre-triage PR and issue ledger
- Verify complete triage coverage and add canonical ledger
- *(maintainer)* Add execution attack plan for the open PR board
- *(audit)* Add Google-style docstrings and split middleware module
- *(export)* Document `zammad_export_tickets` and `ZAMMAD_EXPORT_DIR`
- *(changelog)* Record removal of codex digest automation
- Document `flat_params` helpers and drop the stale `SAFETY_API_KEY` step
- *(tests)* Use single-line docstrings for state-name regression tests
- Order `list_ticket_states` example numerically by id
- *(stats)* Document `counts_truncated` in the tool contract
- *(server)* Advertise lowercase values for `response_format` and `article_type`
- *(server)* Correct `article_type` default and example casing in `add_article`
- *(webhooks)* Document the payload extraction helpers
- Record rate limiting feature in unreleased changelog
- *(changelog)* Regenerate unreleased notes for the merged integration batches
- *(changelog)* Include this branch's own changelog commit in the unreleased notes

### 🎨 Styling

- *(tests)* Annotate shared state fixture as ClassVar (RUF012)
- *(models)* Collapse `_missing_` docstring to one line
- *(server)* Sort merge model imports

### 🧪 Testing

- *(export)* Include `zammad_export_tickets` in tool inventory
- Exercise registered create-ticket tool
- Use tuple form for parametrize argument names
- Cover double quotes in plain-text sanitization
- Cover customer forwarding through `zammad_update_ticket` tool
- Cover attachments in ticket resource and document `pending_time`
- *(models)* Cover non-string enum rejection and ArticleType schema
- *(merge)* Drive `merge_tickets` doubles through the resilient session transport

### ⚙️ Miscellaneous Tasks

- Update tooling and add documentation
- Ignore hookify local config files
- Untrack hookify local configs
- Remove pre-commit from mise config
- *(dependabot)* Tune Python dependency updates
- Declare Python 3.13 and 3.14 support
- *(python)* Pin runtime below 3.14
- Skip Codacy upload for fork PRs
- *(triage)* Add issue and PR automation workflows
- *(hooks)* Silence pre-commit config warning
- *(codacy)* Exclude repo-local codex skills
- *(coderabbit)* Disable automatic PR labeling
- *(codacy)* Strip non-Python tools, sync versions from codacy-cli init
- *(codex)* Add repo-local Codex plugin and drop stale repomix xml
- Replace CLAUDE instructions with AGENTS link
- Update changelog generation
- Align automation with uv and coverage rules
- *(ci)* Delete .github/workflows/sync-labels.yml, stop fighting the factory labels
- Remove obsolete workspace tooling
- Remove legacy Claude commit skill
- *(ci)* Remove CodeRabbit label instructions
- Update mise tool configuration
- Add technical documentation skill
- Enable Entire integrations and record project idea
- Drop accidentally-committed vendor/llm-anon-core gitlink
- Ignore vendor/ and drop accidentally committed gitlink
- Flip docstring layout to satisfy Codacy rule set
- Satisfy Codacy docstring rules (D211/D212/D213/D203)
- Adjust docstring formatting for Codacy
- Satisfy Codacy docstring rules
- Align docstrings with Codacy checks
- Flip docstrings for Codacy
- Report an aggregate test-and-coverage check for the ruleset
- *(triage)* Remove repo-local codex digest automation
- *(plugins)* Complete repo-local plugin retirement
- *(mise)* Pin uv 0.12.20 to match the workflow setup-uv version
- *(codacy)* Exclude tests from the active .codacy.yaml
- Add lint and type-check job to mirror local gates
- Add canonical non-mutating validation script shared by local and CI
- Make validate.sh abort on the first failing gate
- Keep one canonical validation job and flatten new tool docstrings
- *(changelog)* Treat only vN.N.N tags as releases

### 🛡️ Security

- Raise pyjwt floor to 2.14.0 for GHSA-w6j9-cwv2-h6wq

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
