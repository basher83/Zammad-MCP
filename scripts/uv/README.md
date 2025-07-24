# UV Scripts

This directory contains UV single-file scripts that provide development and operational tools for the Zammad MCP project.

## Environment Validation

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
1. **Markdown**: GitHub-flavored markdown with emoji indicators, suitable for PR comments
1. **HTML**: Interactive dashboard with pie charts, bar graphs, and detailed tables

**Exit Codes:**

## Script Execution

These scripts can be executed in several ways:

### Direct Execution (Recommended for GNU/Linux)

```bash
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
1. **UV Installation**: Checks for UV and offers to install if missing
1. **Virtual Environment**: Creates or recreates .venv
1. **Configuration**: Interactive prompts for Zammad credentials
1. **Dependencies**: Installs all project and dev dependencies
1. **Validation**: Runs basic checks to ensure setup success
1. **Next Steps**: Shows helpful commands and resources

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
# etc.
```

### Using UV directly (Most Portable)

```bash
uv run --script dev-setup.py
uv run --script test-zammad.py
# etc.
```

When you run a UV script, UV automatically:

1. Creates an isolated virtual environment
1. Installs the specified dependencies
1. Runs the script with the correct Python version

## Cross-Platform Considerations

The scripts use the shebang `#!/usr/bin/env -S uv run --script`. The `-S` flag is a GNU coreutils extension that allows passing multiple arguments through env.

### Platform Compatibility

- ✅ **Linux (GNU coreutils)**: Full support
- ❌ **macOS (BSD env)**: No `-S` flag support
- ❌ **Alpine (BusyBox)**: No `-S` flag support
- ❌ **FreeBSD/OpenBSD**: No `-S` flag support

  1. Create a new `.py` file in this directory
  1. Add the shebang: `#!/usr/bin/env -S uv run --script`
  1. Add script metadata with dependencies
  1. Make it executable: `chmod +x script.py`

### Workarounds for Non-GNU Systems

1. **Use UV directly** (recommended):

   ```bash
   uv run --script scriptname.py
   ```

1. **Create an alias**:

   ```bash
   alias dev-setup='uv run --script ~/path/to/dev-setup.py'
   ```

1. **Create a wrapper script**:

   ```bash
   #!/bin/sh
   exec uv run --script "$(dirname "$0")/scriptname.py" "$@"
   ```

## Available Scripts

- **dev-setup.py**: Interactive development environment setup wizard
- **test-zammad.py**: Test Zammad API connections and operations
- **validate-env.py**: Validate environment configuration
- **coverage-report.py**: Generate enhanced coverage reports
- **security-scan.py**: Run consolidated security scans

## Script Dependencies

Each script declares its dependencies in the script metadata section. UV automatically manages these dependencies in isolated environments, ensuring no conflicts with your system packages.
