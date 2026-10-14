# Contributing to Zammad MCP Server

Thank you for your interest in contributing to the Zammad MCP Server! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- [mise](https://mise.jdx.dev/getting-started.html). `mise install` installs the pinned Python, uv, prek, git-cliff, and the other tools in `mise.toml`. The `mise run` commands in this guide need it.

### Getting Started

1. Fork the repository

2. Clone your fork:

   ```bash
   git clone https://github.com/YOUR-USERNAME/zammad-mcp.git
   cd zammad-mcp
   ```

3. Install the tools and dependencies:

   ```bash
   mise install            # pinned tools from mise.toml
   mise run setup          # uv sync into .venv
   mise run hooks-install  # pre-commit hooks
   ```

   If mise asks you to trust the repository configuration, run `mise trust`.

   A cloud agent session (for example Claude Code on the web) needs only mise from its environment setup script (`curl https://mise.run | sh`). The repository's SessionStart hook (`.claude/hooks/session-start.sh`) then runs `mise run cloud-setup` and puts the mise shims first on the session PATH. The task installs the tools from `mise.lock` with `--locked`, syncs `.venv` from `uv.lock`, and installs the prek commit hooks. It leaves out the optional Infisical and CodeRabbit steps of `setup` and `hooks-install`.

4. Create a `.env` file with your Zammad credentials:

   ```env
   ZAMMAD_URL=https://your-instance.zammad.com/api/v1
   ZAMMAD_HTTP_TOKEN=your-api-token
   ```

5. (Optional) Validate your environment configuration:

   ```bash
   ./scripts/uv/validate-env.py
   ```

## Development Workflow

### Running the Server

```bash
# Development mode (installed command from pyproject.toml)
uv run mcp-zammad

```

### Code Quality Checks

Before submitting a PR, ensure your code passes all quality checks:

```bash
# Fast non-mutating developer gate: lint + affected tests (CI runs the release variant)
mise run validate

# Run comprehensive quality checks (recommended before a PR; this formats and fixes files)
./scripts/quality-check.sh

# Or run individual checks
uv run ruff format mcp_zammad tests    # Format code
uv run ruff check mcp_zammad tests     # Lint code  
uv run mypy mcp_zammad                 # Type checking
uv run bandit -r mcp_zammad/           # Security scanning
prek run semgrep --all-files           # Security & quality
uv run pip-audit                       # Dependency vulnerability audit

# Run tests (after mise run setup)
uv run pytest

# Run tests with coverage
uv run pytest --cov=mcp_zammad

# Release gates: lint + full coverage suite + build (same as the CI validate job)
mise run validate-release

# Install and run pre-commit hooks (prek, configured in mise.toml)
mise run hooks-install
mise run pre-commit-run
```

### Testing Guidelines

- **Coverage gate**: 86% minimum, configured in `pyproject.toml`
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

The repository includes several GitHub Actions workflows that run automatically to ensure code quality, security, and proper deployment. The Python workflows install uv, and where needed Python, from `mise.toml` and `mise.lock` with `jdx/mise-action`. They use `uv` for Python dependency management.

### Workflow Overview

| Workflow | Purpose | Triggers | Required Secrets |
|----------|---------|----------|------------------|
| **Tests and Coverage** | Runs tests and reports coverage | Push, PR to main, Manual | None |
| **Security Scan** | Python security analysis | Push, PR to main, Weekly (Mon 9:00 UTC), Manual | None |
| **Build and Publish Docker** | Builds and publishes Docker images | Push to main, tags, Manual, PR to main (build only) | None (uses GITHUB_TOKEN) |

### Workflow Details

#### 1. Tests and Coverage (`tests.yml`)

- **Purpose**: Ensures code quality and functionality
- **Jobs**:
  - `validate`: runs `./scripts/validate.sh release` (lint, full coverage suite, package build) on the Python version pinned in `mise.toml`
  - `tests`: runs the full pytest suite with coverage on a Python 3.10, 3.11, 3.12, and 3.13 matrix. Each leg sets `UV_PYTHON` to its version and fails if it runs a different interpreter. It uploads coverage reports as artifacts and writes a coverage summary to the job summary
  - `test-and-coverage`: aggregate required check that fails unless `validate` and every `tests` matrix job succeed
- **Failure conditions**: Any gate in `validate` fails, tests fail, or coverage drops below the `fail_under` floor in `pyproject.toml`
- **Codacy upload**: The `tests` job uploads `coverage.xml` to Codacy only when three conditions are true. The job runs on the Python 3.13 matrix leg, the run is not manual, and the `CODACY_PROJECT_TOKEN` secret is present. Forks and Dependabot PRs pass without the secret

#### 2. Security Scan (`security-scan.yml`)

- **Purpose**: Identifies security vulnerabilities in code and dependencies
- **Tools included**:
  - **Bandit**: Static security analysis for Python code (HIGH/CRITICAL only)
  - **pip-audit**: Dependency vulnerability scanning
- **Reports**: Uploads security reports as artifacts and to GitHub Security tab
- **Configuration**: No additional secrets required
- **Fork Compatibility**: The job runs only in `basher83/Zammad-MCP`. Forks skip it through a repository guard

#### 3. Build and Publish Docker (`docker-publish.yml`)

- **Purpose**: Automated Docker image building and publishing
- **Triggers**:
  - Push to main branch → builds `latest` tag
  - Push tags (v*) → builds version-specific tags
  - Manual dispatch → custom image building
- **Registry**: Publishes to GitHub Container Registry (ghcr.io)
- **Multi-platform**: Builds for linux/amd64 and linux/arm64

### Setting Up Optional Secrets

No workflow requires a repository secret. To enable Codacy coverage reporting:

1. Go to Settings → Secrets and variables → Actions
2. Add the following secret:
   - **`CODACY_PROJECT_TOKEN`** (optional): Get from your Codacy project settings. When the secret is absent, the workflow skips the upload step.

### Workflow Best Practices

- All workflows use pinned action versions with SHA hashes for security
- Dependencies are installed with `uv sync --dev --frozen` for reproducibility
- The security scan fails the job on Bandit HIGH/CRITICAL findings and on pip-audit vulnerabilities. Only the "Generate Bandit SARIF report" step uses `continue-on-error: true`, so the Security tab upload runs even when that report step fails
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
- **MyPy**: Project type-checking rules are configured in `pyproject.toml`

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

Register the tool inside a `ZammadMCPServer._setup_*` method in `server.py`. Define a parameters model in `models.py`, stack `@self.mcp.tool(...)` over `@flat_params(...)` from `mcp_zammad/tool_params.py`, and get the client with `self.get_client()`. Choose the annotation helper that matches the operation: `_read_only_annotations`, `_write_annotations`, `_idempotent_write_annotations`, or `_destructive_write_annotations`. This example follows `zammad_list_knowledge_bases`:

```python
@self.mcp.tool(annotations=_read_only_annotations("List Knowledge Bases"))
@flat_params(ListKnowledgeBasesParams)
def zammad_list_knowledge_bases(params: ListKnowledgeBasesParams) -> str:
    """List all knowledge bases available in Zammad.

    Note:
        Requires knowledge_base.reader or knowledge_base.editor permission.
    """
    client = self.get_client()
    kbs = client.list_knowledge_bases()
    if params.response_format == ResponseFormat.JSON:
        result = json.dumps({"items": kbs, "count": len(kbs)}, indent=2, default=str)
    else:
        lines = ["# Knowledge Bases", "", f"Found {len(kbs)} knowledge base(s)", ""]
        for kb in kbs:
            lines.append(f"## KB ID: {kb.get('id', 'N/A')}")
            lines.append(f"- **Active**: {kb.get('active', False)}")
            lines.append("")
        result = "\n".join(lines)
    return truncate_response(result)
```

The real tool also prints the custom address and root category count for each knowledge base.

Test the tool through the public FastMCP boundary (for example `await server.mcp.get_tool("zammad_list_knowledge_bases")` or a `fastmcp.Client` call) with a mocked `ZammadClient`. Do not assert against private registries.


> **Note**: `get_client()` is auth-aware. When OAuth authentication is
> configured, it automatically creates a per-request `ZammadClient` using
> the authenticated user's Zammad bearer token. No special handling is needed
> in tool implementations.

### 2. New Models

Define in `models.py` using Pydantic:

```python
from pydantic import BaseModel, ConfigDict


class NewModel(BaseModel):
    """Model description."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_name: str
    optional_field: int | None = None
```

Request parameter models extend `StrictBaseModel` in `models.py`, which already sets this `model_config`.

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

# Run the release gates: lint + full coverage suite + build
mise run validate-release

# Generate the release section in CHANGELOG.md from git history (git-cliff).
# Replace X.Y.Z with the new version, without the "v" prefix.
mise run changelog-bump X.Y.Z
```

`changelog-bump` rewrites only the unreleased section of `CHANGELOG.md` and prints the next steps. Follow them:

1. Review `CHANGELOG.md`
1. Update the version in `pyproject.toml`: `uv version X.Y.Z`
1. Commit: `git add CHANGELOG.md pyproject.toml uv.lock && git commit -m 'chore(release): prepare for vX.Y.Z'`

Then create and push the tag as described in the next step.

#### 2. Create and Push a Version Tag

```bash
# Create an annotated semantic version tag (vX.Y.Z format, for example v1.2.0)
git tag -a v1.2.0 -m "Release v1.2.0"

# For pre-releases
git tag -a v1.2.0-beta.1 -m "Pre-release v1.2.0-beta.1"

# Push the commit and the tag to trigger Docker builds
git push && git push --tags
```

#### 3. Automated Docker Publishing

Once the tag is pushed, the GitHub Actions workflow automatically:

- Builds Docker images for multiple platforms (linux/amd64, linux/arm64)
- Creates the following tags in GitHub Container Registry:
  - `ghcr.io/basher83/zammad-mcp:1.2.0` (exact version)
  - `ghcr.io/basher83/zammad-mcp:1.2` (minor version)
  - `ghcr.io/basher83/zammad-mcp:1` (major version)
- Release tags do not update `latest`. Pushes to `main` produce the `latest` tag.

#### 4. Create GitHub Release

After the Docker images are built:

1. Go to [Releases](https://github.com/basher83/Zammad-MCP/releases)
2. Click "Draft a new release"
3. Select your tag (e.g., v1.2.0)
4. Add the release title and copy the notes from the matching `CHANGELOG.md` section
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
git tag -a v1.2.0-beta.1 -m "Pre-release v1.2.0-beta.1"

# Release candidates
git tag -a v1.2.0-rc.1 -m "Pre-release v1.2.0-rc.1"
```

## Priority Areas for Contribution

### Immediate Needs

- ✅ Maintain at least the configured 86% coverage gate
- Fix unused parameters in functions
- SSRF hardening for `ZAMMAD_URL` (the client validates the URL scheme and hostname and warns on local or private addresses, but does not block them)

### Short Term

- Add config file support

### Long Term

- SLA management features
- Async Zammad client

## Questions?

Feel free to:

- Open an issue for discussion
- Ask questions in pull requests
- Refer to the [MCP Documentation](https://modelcontextprotocol.io/)
- Check [Zammad API docs](https://docs.zammad.org/)
