# Codacy CLI v2

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/8cae070168cf488db82478ba6505a005)](https://app.codacy.com/gh/codacy/codacy-cli-v2/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade) [![Codacy Badge](https://app.codacy.com/project/badge/Coverage/8cae070168cf488db82478ba6505a005)](https://app.codacy.com/gh/codacy/codacy-cli-v2/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_coverage)


Codacy CLI (version 2) is a command-line tool for running code analysis and integrating with Codacy. If your repository exists in Codacy, you can sync your configuration to ensure consistency with your organization's standards. 

You can also use Codacy CLI for local code analysis without a Codacy account, leveraging the linter configuration files found in your project's root or Codacy's suggested defaults.

The CLI supports uploading analysis results (in [SARIF](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) format) to Codacy as well.

It is invoked using the `codacy-cli` command and provides several commands for project setup, analysis, and integration.

---

## Supported Platforms

- **macOS**
- **Linux**
- **Windows (via WSL only)**

> **Note:** Native Windows is not yet supported. For Windows, use [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/) and follow the Linux instructions inside your WSL terminal.

---

## Installation

### macOS (Homebrew)

```bash
brew install codacy/codacy-cli-v2/codacy-cli-v2
```

### Linux / Windows (WSL)

Run the following in your terminal (Linux or WSL):

```bash
bash <(curl -Ls https://raw.githubusercontent.com/codacy/codacy-cli-v2/main/codacy-cli.sh)
```

Or create an alias for convenience:

```bash
alias codacy-cli="bash <(curl -Ls https://raw.githubusercontent.com/codacy/codacy-cli-v2/main/codacy-cli.sh)"
```

---

## CLI Commands

### `init` — Bootstrap Project Configuration

Bootstraps the CLI configuration in your project's folder. This command creates a `.codacy` directory containing a `codacy.yaml` file, which specifies the runtimes and tools that will be used and installed.

- If you provide Codacy repository information (API token, provider, organization, repository), the configuration will be fetched from Codacy, ensuring consistency with your organization's standards.
- If no Codacy information is provided, all available tools will be included. For each tool, if a local configuration file exists in your project, it will be used; otherwise, Codacy's suggested defaults will be used.

- **Local mode (local configuration files):**
  ```bash
  codacy-cli init
  ```
- **Remote mode (fetch configuration from Codacy):**
  ```bash
  codacy-cli init --api-token <token> --provider <gh|gl|bb> --organization <org> --repository <repo>
  ```

**Flags:**
- `--api-token` (string): Codacy API token (optional; enables fetching remote config)
- `--provider` (string): Provider (`gh`, `gl`, `bb`), required with `--api-token`
- `--organization` (string): Organization name, required with `--api-token`
- `--repository` (string): Repository name, required with `--api-token`

### `config reset` — Reset Configuration

Resets the Codacy configuration files and tool-specific configurations. This command overwrites existing configuration with either local default configurations or repository-specific configurations from Codacy.

```bash
# Reset to local default configurations
codacy-cli config reset

# Reset to repository-specific configurations from Codacy
codacy-cli config reset --api-token <token> --provider <gh|gl|bb> --organization <org> --repository <repo>
```

**Behavior:**
- **Local mode**: Creates default configurations for all available tools
- **Remote mode**: Fetches and applies repository-specific configurations from Codacy
- Prevents accidental mode switching (remote to local requires explicit flags)
- Overwrites existing `.codacy/codacy.yaml` and tool configurations
- Creates or updates `.codacy/.gitignore` file

**Flags:** Same as `init` command (api-token, provider, organization, repository)

### `config discover` — Discover Project Languages

Scans a project directory to detect programming languages and automatically configures appropriate static analysis tools. This command updates both `languages-config.yaml` and `codacy.yaml` with relevant tools for detected languages.

```bash
# Discover languages in current directory
codacy-cli config discover .

# Discover languages in specific project path
codacy-cli config discover /path/to/project
```

**Features:**
- Automatically detects file extensions and maps them to programming languages
- Updates `.codacy/tools-configs/languages-config.yaml` with discovered languages
- Enables relevant tools in `codacy.yaml` based on detected languages
- Creates tool-specific configuration files for discovered tools
- Works in both local and cloud modes

### `install` — Install Runtimes and Tools

Installs all runtimes and tools specified in `.codacy/codacy.yaml`:
- Downloads and extracts runtimes (Node, Python, Dart, Java, etc.)
- Installs tools (ESLint, Trivy, Pylint, PMD, etc.) using the correct package manager or direct download
- Handles platform-specific details
- Skips already installed components (e.g., Node, Python, Dart, Java, etc.)
- Shows a progress bar and reports any failures

```bash
codacy-cli install
```
- Optionally specify a custom registry:
  ```bash
  codacy-cli install --registry <url>
  ```

### `analyze` — Run Code Analysis

Runs all configured tools, or a specific tool, on your codebase.

```bash
# Run all tools
codacy-cli analyze

# Run a specific tool (e.g., ESLint)
codacy-cli analyze --tool eslint

# Output results in SARIF format
codacy-cli analyze --tool eslint --format sarif

# Store results as SARIF in a file
codacy-cli analyze -t eslint --format sarif -o eslint.sarif

# Analyze a specific file with all configured tools
codacy-cli analyze path/to/file.js

# Analyze a specific file with a specific tool (e.g., ESLint)
codacy-cli analyze --tool eslint path/to/file.js
```

**Flags:**
- `--output, -o`: Output file for the results; if not provided, results will be printed to the console
- `--tool, -t`: Tool to run analysis with (e.g., eslint)
- `--format`: Output format (e.g., `sarif`)
- `--fix`: Automatically fix issues when possible

### `upload` — Upload SARIF Results to Codacy

Uploads a SARIF file containing analysis results to Codacy.

```bash
# With project token
codacy-cli upload -s path/to/your.sarif -c <commit-uuid> -t <project-token>

# With API token
codacy-cli upload -s path/to/your.sarif -c <commit-uuid> -a <api-token> -p <provider> -o <owner> -r <repository>
```

**Flags:**
- `--sarif-path, -s`: Path to the SARIF report (required)
- `--commit-uuid, -c`: Commit UUID
- `--project-token, -t`: Project token for Codacy API
- `--api-token, -a`: User-level token for Codacy API
- `--provider, -p`: Provider name (e.g., gh, gl, bb)
- `--owner, -o`: Repository owner
- `--repository, -r`: Repository name

### `update` — Update the CLI

Fetches and installs the latest version of the CLI.

```bash
codacy-cli update
```

### `version` — Show Version Information

Displays detailed version/build information for the CLI.

```bash
codacy-cli version
```

---

## Configuration

- **`.codacy/codacy.yaml`**: Main configuration file specifying runtimes and tool versions.
- **`.codacy/tools-configs/`**: Tool-specific configuration files (auto-generated or fetched from Codacy).

---

## Example Usage

```bash
# 1. Initialize project (local or remote)
codacy-cli init
# or
codacy-cli init --api-token <token> --provider gh --organization my-org --repository my-repo

# 2. (Optional) Discover languages and configure tools automatically
codacy-cli config discover .

# 3. Install all required runtimes and tools
codacy-cli install

# 4. Run analysis (all tools or specific tool)
codacy-cli analyze
codacy-cli analyze --tool eslint

# 5. Upload results to Codacy
codacy-cli upload -s eslint.sarif -c <commit-uuid> -t <project-token>
```

---

## Troubleshooting

### WSL (Windows Subsystem for Linux)
- **Always use a WSL terminal** (e.g., Ubuntu on Windows) for all commands.
- Ensure you have the latest version of WSL and a supported Linux distribution installed.
- If you see errors related to missing Linux tools (e.g., `curl`, `tar`), install them using your WSL package manager (e.g., `sudo apt install curl tar`).

### MacOS: Errors related to `docker-credential-osxkeychain` not found

Install the docker credential helper:

```bash
brew install docker-credential-helper
```

---

## Example Repository

See [eslint-test-examples](https://github.com/troubleshoot-codacy/eslint-test-examples) for a repository using this CLI in GitHub Actions.

---

## Breaking Changes & Version Pinning

Some behaviors have changed with recent updates. To rely on a specific CLI version, set the following environment variable:

```bash
export CODACY_CLI_V2_VERSION="1.0.0-main.133.3607792"
```

Check the [releases](https://github.com/codacy/codacy-cli-v2/releases) page for all available versions.

---