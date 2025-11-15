# CLAUDE.md

Project-specific guidance for Claude Code when working in this repository.

---

## 📋 Quick Reference Commands

```bash
# Environment setup
mise run setup                    # Complete dev environment setup

# Testing
uv run pytest                     # Run tests
uv run pytest --cov=mcp_zammad   # Run with coverage

# Code quality
uv run ruff format mcp_zammad tests  # Format code
uv run ruff check mcp_zammad tests   # Lint
uv run mypy mcp_zammad              # Type check
./scripts/quality-check.sh          # Run all checks

# Changelog management
mise run changelog                # Update unreleased section
mise run changelog-bump <version> # Prepare release
```

---

## 🔒 Development Rules

**ALWAYS:**

- Use `rg` instead of `grep`
- Use `mise run changelog` to update CHANGELOG.md
- Run quality checks before committing
- Mock `ZammadClient` in tests
- Use Python 3.10+ type syntax: `list[str]` not `List[str]`
- Use modern union syntax: `str | None` not `Optional[str]`

**NEVER:**

- Use bare `grep` command
- Manually edit CHANGELOG.md released sections
- Commit without running pre-commit hooks
- Use deprecated typing module imports

---

## 🏗️ Architecture

**Project Type:** Model Context Protocol (MCP) server for Zammad ticket system

**MCP Version:** 1.21.1 (FastMCP)

**Core Files:**

- `mcp_zammad/server.py` - FastMCP server with 18 tools, 4 resources, 3 prompts
- `mcp_zammad/client.py` - Zammad API wrapper with authentication & validation
- `mcp_zammad/models.py` - Pydantic models for type safety

**Response Formats:**

All data-returning tools support two output formats:

- **Markdown** (default): Human-readable text optimized for LLM consumption
- **JSON**: Complete structured data with all metadata fields

This unification follows MCP best practices for consistent tool output.

**Key Patterns:**

- Dependency injection for client sharing
- Sentinel pattern (`_UNINITIALIZED`) for type safety
- Type narrowing with `get_zammad_client()` helper
- Async-first architecture

---

## ⚙️ Environment Configuration

Required environment variables (see `.env.example`):

```bash
ZAMMAD_URL=https://instance.zammad.com/api/v1  # Must include /api/v1
ZAMMAD_HTTP_TOKEN=your-api-token                # Recommended auth method
```

---

## 🧪 Testing Standards

**Coverage Target:** 90%+ (current: 90.08%)

**Test Organization:**

1. Fixtures at top
1. Basic tests
1. Parametrized tests
1. Error cases

**Requirements:**

- Always mock `ZammadClient` and external dependencies
- Use factory fixtures for test data
- Test validation errors and unhappy paths
- Ensure backward compatibility with wrapper functions

---

## 📐 Code Standards

**Tooling:**

- Ruff (format + lint, 120 char line length)
- MyPy (strict type checking)
- Python 3.10+ required (currently pinned to 3.13)

**Type Annotations:**

```python
# ✅ DO
list[str]
str | None
cast(ZammadClient, client)

# ❌ DON'T
List[str]
Optional[str]
```

**Naming:**

- Avoid parameter shadowing: use `article_type` not `type`

---

## 🔧 Adding New Features

**MCP Components:**

- Tools: Add to `server.py` with `@mcp.tool()` decorator
- Resources: Add handlers in `server.py` (URI: `zammad://entity/id`)
- Prompts: Use `@mcp.prompt()` decorator

**Data Flow:**

1. Define Pydantic model in `models.py`
1. Add client method in `client.py`
1. Create MCP tool in `server.py`
1. Add tests with mocked client

---

## 🔐 Security Notes

**Implemented:**

- URL validation (SSRF protection)
- HTML sanitization (XSS protection)
- Input validation via Pydantic

**Not Implemented:**

- Rate limiting
- Audit logging

---

## 📚 Additional Information

- **Deployment**: See README.md
- **API Documentation**: See docstrings in source files
- **Known Issues**: See GitHub Issues
- **Changelog**: See CHANGELOG.md (managed by git-cliff)
