# GitHub Copilot Instructions for Zammad MCP

This is a Python-based Model Context Protocol (MCP) server that provides integration with the Zammad ticket system. When contributing or using GitHub Copilot in this repository, please follow these guidelines:

## Code Standards

### Language and Framework
- Python 3.10+ with modern type annotations (use `list[str]` not `List[str]`)
- FastMCP framework for MCP server implementation
- Pydantic for data validation and models
- UV for dependency management

### Required Before Each Commit
1. Run quality checks: `./scripts/quality-check.sh`
   - Or individually:
   - Format: `uv run ruff format mcp_zammad tests`
   - Lint: `uv run ruff check mcp_zammad tests`
   - Type check: `uv run mypy mcp_zammad`
   - Security: `uv run bandit -r mcp_zammad/`
1. Run tests: `uv run pytest --cov=mcp_zammad`
1. Ensure coverage target: 80%+ (current: 67%)

## Repository Structure
- `mcp_zammad/`: Core MCP server implementation
  - `server.py`: FastMCP server with tools, resources, and prompts
  - `client.py`: Zammad API client wrapper
  - `models.py`: Pydantic models for all Zammad entities
- `tests/`: Test files (pytest)
- `scripts/`: Development and deployment scripts
  - `uv/`: UV single-file scripts for development tools
- `docs/`: Documentation
- `.claude/`: Claude Code specific configurations

## Key Guidelines

### MCP Implementation
1. Tools use `@mcp.tool()` decorator and return Pydantic models
1. Resources follow URI pattern: `zammad://entity/id`
1. Always validate input with Pydantic models
1. Handle errors gracefully with proper MCP error responses

### Python Best Practices
1. Use modern Python 3.10+ syntax:
   - Union types: `str | None` not `Optional[str]`
   - Type hints for all functions and methods
   - Avoid parameter shadowing (use `article_type` not `type`)
1. Follow single responsibility principle
1. Use dependency injection pattern (see `get_zammad_client()`)
1. Explicit type casts when needed: `cast(ZammadClient, client)`

### Testing
1. Mock `ZammadClient` in all tests
1. Test both happy and error paths
1. Use parametrized tests for multiple scenarios
1. Group fixtures at top, then basic tests, then error cases

### Security Considerations
1. Never commit credentials or tokens
1. Validate all user inputs
1. Use environment variables for configuration
1. Run security scans before committing

### Documentation
1. Update CLAUDE.md for AI-specific guidance
1. Document new tools/resources in docstrings
1. Keep README.md updated for new features
1. Add type hints and docstrings to all public APIs

## Common Tasks

### Adding a New Tool
```python
@mcp.tool()
def tool_name(param: str) -> ModelType:
    """Clear description of tool purpose."""
    client = get_zammad_client()
    # Implementation
    return ModelType(...)
```

### Adding a New Model
```python
class NewModel(BaseModel):
    """Model description."""
    field: str
    optional: int | None = None
    
    class Config:
        extra = "forbid"
```

## Copilot-Specific Tips

When using GitHub Copilot in this repository:

1. **Context Awareness**: Copilot should recognize MCP patterns and suggest appropriate decorators
1. **Type Safety**: Always suggest proper type hints following Python 3.10+ syntax
1. **Error Handling**: Suggest try/except blocks with proper MCP error responses
1. **Test Generation**: When creating new functions, also suggest corresponding tests
1. **Import Organization**: Follow existing import patterns (standard lib, third-party, local)
1. **Pydantic Models**: When working with API responses, suggest Pydantic model creation

## Environment Setup
- Use UV for dependency management
- Python 3.10+ required
- Set Zammad credentials in `.env` file
- Run `./scripts/uv/dev-setup.py` for interactive setup

Remember: This is an MCP server, not a standalone application. All features should be exposed through MCP tools, resources, or prompts.