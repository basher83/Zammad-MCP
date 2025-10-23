# Contributing to Zammad MCP Server

Thank you for your interest in contributing to the Zammad MCP Server! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- `uv` package manager:
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  
  # Windows
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

### Getting Started

1. Fork the repository
2. Clone your fork:

   ```bash
   git clone https://github.com/YOUR-USERNAME/zammad-mcp.git
   cd zammad-mcp
   ```

#### Quick Start (Recommended)

Use the interactive setup wizard for the easiest setup experience:

```bash
./scripts/uv/dev-setup.py
```

This wizard will guide you through all setup steps including UV installation, virtual environment creation, and configuration.

#### Manual Setup

If you prefer manual setup:

1. (Optional) Install recommended development tools:

   ```bash
   # Install eza, ripgrep, and ensure uv is available
   ./scripts/bootstrap.sh
   ```

2. Run the Python environment setup script:

   ```bash
   # macOS/Linux
   ./scripts/setup.sh
   
   # Windows
   .\scripts\setup.ps1
   ```

3. Create a `.env` file with your Zammad credentials:

   ```env
   ZAMMAD_URL=https://your-instance.zammad.com/api/v1
   ZAMMAD_HTTP_TOKEN=your-api-token
   ```

4. (Optional) Validate your environment configuration:

   ```bash
   ./scripts/uv/validate-env.py
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
uv run safety scan --output json       # Dependency vulnerabilities
uv run pip-audit                       # Additional dependency audit

# Run tests
uv run pytest --cov=mcp_zammad

# Install and run pre-commit hooks
uv run pre-commit install
uv run pre-commit run --all-files
```

### Testing Guidelines

- **Current Coverage**: 91.7% (exceeds target of 80%!)
- Write tests for all new features
- Maintain or improve the current high coverage level
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

## GitHub Workflows / CI/CD Pipeline

The repository includes several GitHub Actions workflows that run automatically to ensure code quality, security, and proper deployment. All workflows use `uv` for Python dependency management.

### Workflow Overview

| Workflow | Purpose | Triggers | Required Secrets |
|----------|---------|----------|------------------|
| **Tests and Coverage** | Runs tests and reports coverage | Push, PR to main | None |
| **Security Scan** | Python security analysis | Push, PR to main, Weekly (Mon 9:00 UTC) | `SAFETY_API_KEY` |
| **Codacy Security Scan** | Comprehensive code analysis | Push, PR to main, Weekly (Thu 5:28 UTC) | `CODACY_PROJECT_TOKEN`, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` |
| **Build and Publish Docker** | Builds and publishes Docker images | Push to main, tags, Manual | None (uses GITHUB_TOKEN) |
| **Copilot Setup Steps** | Development environment setup | Manual only | None |

### Workflow Details

#### 1. Tests and Coverage (`tests.yml`)

- **Purpose**: Ensures code quality and functionality
- **What it does**:
  - Runs the full test suite with pytest
  - Generates coverage reports
  - Uploads coverage results as artifacts
  - Comments coverage on PRs (if configured)
- **Failure conditions**: Tests fail or coverage drops below threshold
- **Fork Compatibility**: Workflow automatically handles missing secrets in forked repositories without failing

#### 2. Security Scan (`security-scan.yml`)

- **Purpose**: Identifies security vulnerabilities in code and dependencies
- **Tools included**:
  - **Bandit**: Static security analysis for Python code (HIGH/CRITICAL only)
  - **Safety**: Dependency vulnerability scanning (requires API key)
  - **pip-audit**: Additional dependency security checks
- **Reports**: Uploads security reports as artifacts and to GitHub Security tab
- **Configuration**: Set `SAFETY_API_KEY` in repository secrets (get from <https://safetycli.com>)
- **Fork Compatibility**: Workflow automatically handles missing secrets in forked repositories without failing

#### 3. Codacy Security Scan (`codacy.yml`)

- **Purpose**: Comprehensive code quality and security analysis
- **What it does**:
  - Runs Codacy's full analysis suite
  - Uploads results to GitHub Security tab as SARIF
  - Integrates with PR checks
- **Configuration**: 
  - Set `CODACY_PROJECT_TOKEN` in repository secrets
  - Set `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` to avoid Docker Hub rate limits
  - Note: Without Docker Hub authentication, the workflow may fail due to rate limits when pulling analysis images
- **Fork Compatibility**: Workflow automatically handles missing secrets in forked repositories without failing

#### 4. Build and Publish Docker (`docker-publish.yml`)

- **Purpose**: Automated Docker image building and publishing
- **Triggers**:
  - Push to main branch → builds `latest` tag
  - Push tags (v*) → builds version-specific tags
  - Manual dispatch → custom image building
- **Registry**: Publishes to GitHub Container Registry (ghcr.io)
- **Multi-platform**: Builds for linux/amd64 and linux/arm64

#### 5. Copilot Setup Steps (`copilot-setup-steps.yml`)

- **Purpose**: Development environment setup guide
- **Usage**: Manual trigger only - provides setup instructions
- **Useful for**: New contributors getting started

### Setting Up Required Secrets

To configure the required secrets:

1. Go to Settings → Secrets and variables → Actions
2. Add the following secrets:
   - **`SAFETY_API_KEY`**: Sign up at <https://safetycli.com/resources/plans>
   - **`CODACY_PROJECT_TOKEN`**: Get from your Codacy project settings

### Workflow Best Practices

- All workflows use pinned action versions with SHA hashes for security
- Dependencies are installed with `uv sync --dev --frozen` for reproducibility
- Security scans use `continue-on-error: true` to capture reports even on failure
- Test workflows should fail fast on errors
- Use job summaries (`$GITHUB_STEP_SUMMARY`) for clear status reporting

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

```text
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
1. Make your changes following the guidelines above
1. Add tests for new functionality
1. Update documentation as needed
1. Run all quality checks
1. Commit with clear messages
1. Push and create a PR with:
   - Clear description of changes
   - Link to related issues
   - Test results/coverage report

## Release Process

### Creating a New Release

Releases are managed through git tags, which automatically trigger Docker image builds with proper versioning.

#### 1. Prepare the Release

```bash
# Ensure you're on main branch with latest changes
git checkout main
git pull origin main

# Run all quality checks
./scripts/quality-check.sh

# Update CHANGELOG.md with release notes
# Update version in pyproject.toml if needed
```

#### 2. Create and Push a Version Tag

```bash
# Create a semantic version tag (vX.Y.Z format)
git tag v1.0.0 -m "Release version 1.0.0"

# For pre-releases
git tag v1.0.0-beta.1 -m "Pre-release version 1.0.0-beta.1"

# Push the tag to trigger Docker builds
git push origin v1.0.0
```

#### 3. Automated Docker Publishing

Once the tag is pushed, the GitHub Actions workflow automatically:

- Builds Docker images for multiple platforms (linux/amd64, linux/arm64)
- Creates the following tags in GitHub Container Registry:
  - `ghcr.io/basher83/zammad-mcp:1.0.0` (exact version)
  - `ghcr.io/basher83/zammad-mcp:1.0` (minor version)
  - `ghcr.io/basher83/zammad-mcp:1` (major version)
  - `ghcr.io/basher83/zammad-mcp:latest` (if this is the latest release)

#### 4. Create GitHub Release

After the Docker images are built:

1. Go to [Releases](https://github.com/basher83/Zammad-MCP/releases)
2. Click "Draft a new release"
3. Select your tag (e.g., v1.0.0)
4. Add release title and notes from CHANGELOG.md
5. Publish the release

### Version Numbering Guidelines

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes to the MCP interface
- **MINOR** (1.X.0): New features, backward compatible
- **PATCH** (1.0.X): Bug fixes, backward compatible

### Pre-release Versions

For testing releases before making them stable:

```bash
# Beta releases
git tag v1.0.0-beta.1

# Release candidates
git tag v1.0.0-rc.1
```

## Priority Areas for Contribution

### Immediate Needs

- ✅ ~~Increase test coverage to 80%+~~ (Achieved: 91.7%!)
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
