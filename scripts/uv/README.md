# UV Single-File Scripts

This directory contains UV single-file scripts that enhance the Zammad MCP development workflow. These scripts are self-contained Python files with inline dependency management using UV.

## Available Scripts

### validate-env.py

Validates the Zammad MCP Server environment configuration before startup.

**Features:**
- Checks environment variables are properly set
- Validates Zammad URL format
- Tests API connection and authentication
- Displays user information on successful connection
- Rich CLI output with tables and progress indicators
- JSON output mode for CI/CD integration

**Usage:**

```bash
# Interactive mode with default .env file
./validate-env.py

# Use custom environment file
./validate-env.py --env-file custom.env

# Skip connection test (only validate syntax)
./validate-env.py --no-test-connection

# JSON output for automation
./validate-env.py --json

# Run with uv directly (no need to make executable)
uv run scripts/uv/validate-env.py
```

**Exit Codes:**
- 0: Configuration valid (and connection successful if tested)
- 1: Configuration errors or connection failed

### coverage-report.py

Generates beautiful, actionable coverage reports beyond basic terminal output.

**Features:**
- Parses coverage.xml data from pytest-cov
- Multiple output formats:
  - Rich terminal output with tables and trees
  - Markdown reports perfect for PR comments
  - HTML dashboards with visualization charts
- Shows uncovered lines grouped by file
- Compares coverage against configurable targets
- Tracks coverage history over time
- Color-coded output based on coverage thresholds

**Usage:**

```bash
# Generate coverage data first
uv run pytest --cov=mcp_zammad --cov-report=xml

# Terminal report with Rich formatting
./coverage-report.py

# Show uncovered lines
./coverage-report.py --show-uncovered

# Generate markdown for PR comments
./coverage-report.py --format markdown --output coverage.md

# Generate HTML dashboard with charts
./coverage-report.py --format html --output coverage.html

# Compare against custom target (default: 80%)
./coverage-report.py --compare-to 90

# Save coverage history for trend tracking
./coverage-report.py --save-history
```

**Output Examples:**

1. **Terminal**: Rich tables showing file-by-file coverage, overall summary, and optional uncovered line details
2. **Markdown**: GitHub-flavored markdown with emoji indicators, suitable for PR comments
3. **HTML**: Interactive dashboard with pie charts, bar graphs, and detailed tables

**Exit Codes:**
- 0: Coverage meets target
- 1: Coverage below target or error parsing coverage file

### dev-setup.py

Interactive setup wizard for new contributors to get started quickly.

**Features:**
- System requirements verification (Python 3.10+, Git, OS compatibility)
- Automatic UV installation if not present
- Virtual environment creation and management
- Interactive .env configuration with guided prompts
- Dependency installation with progress tracking
- Setup validation and initial tests
- Comprehensive next steps guidance
- Cross-platform support (Windows, macOS, Linux)

**Usage:**

```bash
# Run interactive setup wizard
./dev-setup.py

# Quick setup with minimal prompts
./dev-setup.py --quick

# Only check requirements without running setup
./dev-setup.py --check-only

# Run with uv directly
uv run scripts/uv/dev-setup.py
```

**Setup Flow:**
1. **System Check**: Verifies Python version, Git, and project structure
2. **UV Installation**: Checks for UV and offers to install if missing
3. **Virtual Environment**: Creates or recreates .venv
4. **Configuration**: Interactive prompts for Zammad credentials
5. **Dependencies**: Installs all project and dev dependencies
6. **Validation**: Runs basic checks to ensure setup success
7. **Next Steps**: Shows helpful commands and resources

**Exit Codes:**
- 0: Setup completed successfully
- 1: Setup failed or was cancelled

### security-scan.py

Unified security scanner that consolidates multiple security tools into a single actionable report.

**Features:**
- Runs multiple security scanners:
  - **pip-audit**: Vulnerability scanning for Python dependencies
  - **bandit**: Static security analysis for Python code
  - **safety**: Additional dependency vulnerability checking
  - **semgrep**: Advanced static analysis with security rules
- Unified reporting with consistent severity levels (Critical/High/Medium/Low/Info)
- Multiple output formats:
  - Rich terminal output with color-coded severity
  - JSON for programmatic processing
  - SARIF for GitHub Actions integration
- Detailed remediation suggestions for each issue
- Filtering by minimum severity level
- Support for running individual tools

**Usage:**

```bash
# Run all security scans
./security-scan.py

# Run specific tools only
./security-scan.py --tool pip-audit --tool bandit

# Show only high severity and above
./security-scan.py --severity high

# Generate SARIF report for GitHub
./security-scan.py --format sarif --output security.sarif

# JSON output for CI/CD pipelines
./security-scan.py --format json --output security.json

# Future: Apply automatic fixes
./security-scan.py --fix
```

**Security Issue Details:**
- **Tool**: Which scanner found the issue
- **Severity**: Critical/High/Medium/Low/Info rating
- **Location**: File path and line number or package name
- **Details**: CVE/CWE IDs, confidence levels, fix versions
- **Remediation**: Specific steps to fix the issue

**Exit Codes:**
- 0: No critical/high severity issues found
- 1: Critical or high severity issues detected

### test-zammad.py

Interactive CLI for testing Zammad API connections and operations without the MCP server.

**Features:**
- **Interactive Mode**: Menu-driven interface for exploring the API
- **Connection Testing**: Validates credentials and displays connection timing
- **API Operations**:
  - List tickets with filtering and pagination
  - Get detailed ticket information with articles
  - Create test tickets interactively
  - Search users by query
  - List groups, states, and priorities
- **Performance Benchmarking**: Runs timed tests on common operations
- **Multiple Auth Support**: HTTP token, OAuth2, or username/password
- **Rich Terminal UI**: Tables, progress bars, and formatted output
- **Non-Interactive Mode**: Run specific operations from command line

**Usage:**

```bash
# Interactive mode (default)
./test-zammad.py

# Run specific operations
./test-zammad.py --operation list-tickets --limit 20
./test-zammad.py --operation list-users
./test-zammad.py --operation benchmark

# Use custom environment file
./test-zammad.py --env-file production.env

# Quick benchmark
./test-zammad.py --benchmark
```

**Interactive Mode Options:**
- List tickets (with optional state filtering)
- Get ticket details (shows articles and metadata)
- Create test ticket (guided ticket creation)
- Search users (by name, email, or wildcard)
- List groups/states/priorities
- Run performance benchmark
- Show API configuration

**Benchmark Tests:**
- Get current user
- List first 10 tickets
- List all groups
- List ticket states
- List priorities

**Exit Codes:**
- 0: Successful connection and operations
- 1: Connection failed or configuration error

## How UV Scripts Work

UV scripts use inline metadata to declare their dependencies:

```python
# /// script
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "httpx>=0.25.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.10"
# ///
```

When you run a UV script, UV automatically:
1. Creates an isolated virtual environment
2. Installs the specified dependencies
3. Runs the script with the correct Python version

## Benefits

- **No Manual Setup**: Dependencies are automatically managed
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Isolated**: Each script has its own environment
- **Type-Safe**: Full Python IDE support with type hints
- **Fast**: UV caches environments for quick subsequent runs

## Creating New Scripts

1. Create a new `.py` file in this directory
2. Add the shebang: `#!/usr/bin/env -S uv run --script`
3. Add script metadata with dependencies
4. Make it executable: `chmod +x script.py`

Example template:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "click>=8.0.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.10"
# ///
"""Script description."""

import click
from rich.console import Console

console = Console()

@click.command()
def main():
    """Main function."""
    console.print("[green]Hello from UV script![/green]")

if __name__ == "__main__":
    main()
```

## Planned Scripts

- `release.py` - Automated release management
- `test-zammad.py` - Interactive Zammad API testing
- `coverage-report.py` - Enhanced coverage reporting
- `security-scan.py` - Consolidated security scanning
- `dev-setup.py` - Interactive development setup
- `issue-helper.py` - GitHub issue template generator
- `profile-zammad.py` - Performance profiling tool

See [docs/uv-scripts-opportunities.md](../../docs/uv-scripts-opportunities.md) for detailed proposals.