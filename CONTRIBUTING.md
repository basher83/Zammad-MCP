# Contributing to Zammad MCP Server

Thank you for your interest in contributing to the Zammad MCP Server! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- `uv` package manager ([installation instructions](https://github.com/astral-sh/uv))

### Getting Started

1. Fork the repository
2. Clone your fork:

   ```bash
   git clone https://github.com/YOUR-USERNAME/zammad-mcp.git
   cd zammad-mcp
   ```

3. (Optional) Install recommended development tools:

   ```bash
   # Install eza, ripgrep, and ensure uv is available
   ./scripts/bootstrap.sh
   ```

4. Run the Python environment setup script:

   ```bash
   # macOS/Linux
   ./scripts/setup.sh
   
   # Windows
   .\scripts\setup.ps1
   ```

5. Create a `.env` file with your Zammad credentials:

   ```env
   ZAMMAD_URL=https://your-instance.zammad.com
   ZAMMAD_HTTP_TOKEN=your-api-token
   ```

## Development Workflow

### Running the Server

```bash
# Development mode
uv run python -m mcp_zammad

# Or directly
python -m mcp_zammad
```

### Code Quality Checks

Before submitting a PR, ensure your code passes all quality checks:

```bash
# Run comprehensive quality checks (recommended)
./scripts/quality-check.sh

# Or run individual checks
uv run ruff format mcp_zammad tests    # Format code
uv run ruff check mcp_zammad tests     # Lint code  
uv run mypy mcp_zammad                 # Type checking
uv run bandit -r mcp_zammad/           # Security scanning
uv run semgrep --config=auto mcp_zammad/ # Security & quality
uv run safety check                    # Dependency vulnerabilities
uv run pip-audit                       # Additional dependency audit

# Run tests
uv run pytest --cov=mcp_zammad

# Install and run pre-commit hooks
uv run pre-commit install
uv run pre-commit run --all-files
```

### Testing Guidelines

- **Current Coverage**: 67% (target: 80%+)
- Write tests for all new features
- Follow the existing test patterns:
  - Group fixtures at the top of test files
  - Organize tests: basic → parametrized → error cases
  - Always mock external dependencies (especially `ZammadClient`)
  - Test both happy and unhappy paths

#### Test Organization Pattern

```python
# Fixtures
@pytest.fixture
def reset_client():
    """Reset global client state."""
    ...

@pytest.fixture
def mock_zammad_client():
    """Mock the Zammad client."""
    ...

# Basic tests
def test_basic_functionality():
    ...

# Parametrized tests
@pytest.mark.parametrize("input,expected", [...])
def test_multiple_scenarios(input, expected):
    ...

# Error cases
def test_error_handling():
    ...
```

## Code Style Guidelines

### Python Version and Type Annotations

- Use Python 3.10+ syntax
- Modern type annotations:

  ```python
  # Good
  def process_items(items: list[str]) -> dict[str, Any]:
      ...
  
  # Bad (old style)
  def process_items(items: List[str]) -> Dict[str, Any]:
      ...
  ```

- Use union syntax: `str | None` instead of `Optional[str]`
- Avoid parameter shadowing: use `article_type` not `type`

### Code Formatting

- **Ruff format**: 120-character line length
- **Ruff**: Extensive rule set (see `pyproject.toml`)
- **MyPy**: Strict type checking enabled

### Commit Messages

Follow conventional commit format:

```plaintext
feat: add attachment support for tickets
fix: resolve memory leak in get_ticket_stats
docs: update README with uvx instructions
test: add coverage for error cases
```

## Adding New Features

### 1. New Tools

Add to `server.py` using the `@mcp.tool()` decorator:

```python
@mcp.tool()
def new_tool_name(param1: str, param2: int) -> ReturnType:
    """Clear description of what the tool does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
    """
    client = get_zammad_client()
    # Implementation
```

### 2. New Models

Define in `models.py` using Pydantic:

```python
class NewModel(BaseModel):
    """Model description."""
    
    field_name: str
    optional_field: int | None = None
    
    class Config:
        """Pydantic config."""
        extra = "forbid"
```

### 3. New API Methods

Extend `client.py` with new Zammad operations:

```python
def new_api_method(self, param: str) -> dict[str, Any]:
    """Method description."""
    return dict(self.api.resource.method(param))
```

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes following the guidelines above
3. Add tests for new functionality
4. Update documentation as needed
5. Run all quality checks
6. Commit with clear messages
7. Push and create a PR with:
   - Clear description of changes
   - Link to related issues
   - Test results/coverage report

## Priority Areas for Contribution

### Immediate Needs

- Increase test coverage to 80%+
- Fix unused parameters in functions
- Implement custom exception classes
- Add proper URL validation

### Short Term

- Add attachment support
- Implement caching layer
- Add config file support
- Optimize `get_ticket_stats` performance

### Long Term

- Webhook support for real-time updates
- Bulk operations
- SLA management features
- Async Zammad client

## Questions?

Feel free to:

- Open an issue for discussion
- Ask questions in pull requests
- Refer to the [MCP Documentation](https://modelcontextprotocol.io/)
- Check [Zammad API docs](https://docs.zammad.org/)
