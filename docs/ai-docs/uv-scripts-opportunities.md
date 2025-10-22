# UV Single-File Scripts Opportunities for Zammad MCP

## Executive Summary

This document analyzes opportunities to enhance the Zammad MCP project workflows using UV single-file scripts. UV scripts offer self-contained, dependency-managed Python scripts that can replace complex bash scripts, provide better cross-platform compatibility, and improve developer experience through type hints, better error handling, and rich CLI interfaces.

## Current Workflow Analysis

### Existing Scripts

The project currently uses bash scripts for:

- **Setup** (`setup.sh`, `setup.ps1`) - Environment initialization
- **Quality Checks** (`quality-check.sh`) - Running linters, formatters, and tests
- **Bootstrap** (`bootstrap.sh`) - Installing development tools

### Pain Points Identified

1. **Platform Dependency**: Separate scripts needed for Windows (`.ps1`) and Unix (`.sh`)
1. **Error Handling**: Limited error handling in bash scripts
1. **No Type Safety**: Bash scripts lack type checking and IDE support
1. **Complex Operations**: Some tasks (like version bumping, changelog management) are difficult in bash
1. **Dependency Management**: External tools must be installed separately
1. **Limited Interactivity**: Bash scripts offer basic user interaction

## Opportunities Identified

### 1. Release Helper Script (`release.py`)

**Purpose**: Automate the release process including version bumping, changelog updates, and git tagging.

**Features**:

- Interactive or CLI-driven version selection (major/minor/patch)
- Automatic CHANGELOG.md updates with commit parsing
- Git tag creation and optional push
- Pre-release validation checks

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "tomli-w>=1.0.0",
#   "semver>=3.0.0",
#   "click>=8.0.0",
#   "rich>=13.0.0",
#   "gitpython>=3.1.0",
# ]
# ///
```

**Benefits**:

- Consistent release process
- Reduced manual errors
- Automatic semantic versioning
- Beautiful CLI output with Rich

### 2. Zammad Test Client (`test-zammad.py`)

**Purpose**: Interactive CLI for testing Zammad API connections and operations without starting the full MCP server.

**Features**:

- Load credentials from .env
- Test authentication methods
- Execute common API operations
- Display formatted results
- Performance timing

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "click>=8.0.0",
#   "rich>=13.0.0",
#   "python-dotenv>=1.0.0",
#   "httpx>=0.25.0",
#   "zammad-py>=3.2.0",
# ]
# ///
```

**Benefits**:

- Quick API testing
- Troubleshoot connection issues
- Validate credentials
- Test API changes

### 3. Coverage Report Generator (`coverage-report.py`)

**Purpose**: Generate beautiful, actionable coverage reports beyond basic terminal output.

**Features**:

- Parse coverage.xml data
- Generate markdown reports for PR comments
- Create visual HTML dashboards
- Identify untested code paths
- Track coverage trends

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "coverage[toml]>=7.0.0",
#   "jinja2>=3.0.0",
#   "rich>=13.0.0",
#   "matplotlib>=3.5.0",
# ]
# ///
```

**Benefits**:

- Better coverage visibility
- Actionable insights
- PR-friendly reports
- Coverage trend tracking

### 4. Security Scanner (`security-scan.py`)

**Purpose**: Unified security scanning with consolidated, actionable output.

**Features**:

- Run all security tools (bandit, safety, pip-audit, semgrep)
- Aggregate results into single report
- Categorize by severity
- Generate SARIF format for GitHub integration
- Provide remediation suggestions

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "pip-audit>=2.6.0",
#   "bandit[sarif]>=1.7.6",
#   "safety>=2.3.1",
#   "rich>=13.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
```

**Benefits**:

- Single command for all security checks
- Unified reporting format
- GitHub Actions integration
- Clear remediation paths

### 5. Environment Validator (`validate-env.py`)

**Purpose**: Validate Zammad configuration before server startup.

**Features**:

- Check .env file exists and is valid
- Test Zammad API connection
- Validate authentication credentials
- Check required permissions
- Display connection diagnostics

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "python-dotenv>=1.0.0",
#   "httpx>=0.25.0",
#   "rich>=13.0.0",
#   "pydantic>=2.0.0",
# ]
# ///
```

**Benefits**:

- Fast feedback on configuration issues
- Reduced debugging time
- Clear error messages
- Connection troubleshooting

### 6. Development Setup Wizard (`dev-setup.py`)

**Purpose**: Interactive setup guide for new contributors.

**Features**:

- Check system requirements
- Install uv if needed
- Create virtual environment
- Configure .env interactively
- Run initial tests
- Provide next steps

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "click>=8.0.0",
#   "rich>=13.0.0",
#   "python-dotenv>=1.0.0",
#   "questionary>=2.0.0",
# ]
# requires-python = ">=3.10"
# ///
```

**Benefits**:

- Smooth onboarding
- Reduced setup errors
- Interactive guidance
- Cross-platform support

### 7. Issue Template Generator (`issue-helper.py`)

**Purpose**: Generate properly formatted GitHub issues.

**Features**:

- Interactive issue creation
- Template selection (bug, feature, etc.)
- Automatic label assignment
- Environment info collection
- Direct GitHub API submission

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "PyGithub>=2.0.0",
#   "click>=8.0.0",
#   "rich>=13.0.0",
#   "questionary>=2.0.0",
# ]
# ///
```

**Benefits**:

- Standardized issue format
- Complete bug reports
- Reduced back-and-forth
- Automatic labeling

### 8. Performance Profiler (`profile-zammad.py`)

**Purpose**: Profile MCP server performance under various workloads.

**Features**:

- Define test scenarios
- Measure operation latency
- Memory usage tracking
- Generate performance reports
- Compare against baselines

**Script Metadata**:

```python
# /// script
# dependencies = [
#   "pytest-benchmark>=4.0.0",
#   "memory-profiler>=0.60.0",
#   "matplotlib>=3.5.0",
#   "rich>=13.0.0",
#   "pandas>=2.0.0",
# ]
# ///
```

**Benefits**:

- Identify bottlenecks
- Track performance regressions
- Optimize critical paths
- Data-driven improvements

## Implementation Benefits

### Developer Experience

1. **IDE Support**: Full Python IDE features (autocomplete, type checking, refactoring)
1. **Debugging**: Standard Python debugging tools work with UV scripts
1. **Cross-Platform**: Single script works on all platforms
1. **Self-Documenting**: Type hints and docstrings provide inline documentation

### Maintenance Benefits

1. **Dependency Management**: Dependencies declared in script, no separate requirements

1. **Version Locking**: UV lock files ensure reproducibility
1. **Error Handling**: Python's exception handling provides better error messages
1. **Testing**: Scripts can be unit tested like regular Python code
   - Core library modules: 90% coverage target
   - Interactive CLI scripts: 70% coverage target (excluding `__main__` blocks)
   - Focus on testing business logic, not UI interactions
1. **Quality Assurance**: Scripts run through same quality pipeline as main code


### Operational Benefits

1. **No Installation**: Scripts can run directly with `uv run script.py`
1. **Isolated Environments**: Each script gets its own isolated environment
1. **Fast Execution**: UV's caching makes subsequent runs faster
1. **CI/CD Friendly**: Easy to integrate into GitHub Actions

## Migration Strategy

### Phase 1: Pilot Scripts (Week 1-2)

1. Start with `validate-env.py` as proof of concept
1. Implement `coverage-report.py` for immediate value
1. Gather feedback from contributors


### Phase 2: Core Development Tools (Week 3-4)

1. Implement `dev-setup.py` to improve onboarding
1. Create `security-scan.py` to consolidate security checks
1. Develop `test-zammad.py` for API testing


**Success Criteria**:

- All scripts integrated into CI/CD pipeline
- Zero CI failures caused by UV scripts for 5 consecutive days
- Successfully onboard 1 new contributor using `dev-setup.py`


### Phase 3: Advanced Tools (Week 5-6)

1. Build `release.py` for release automation
1. Add `profile-zammad.py` for performance testing
1. Create `issue-helper.py` for better issue management

=======

**Go/No-Go Decision Point**:

- ✅ All UV scripts stable in CI for ≥2 weeks
- ✅ No rollbacks needed in Phase 1 or 2
- ✅ Team consensus on proceeding
- ❌ If any criterion fails: Pause and address issues


### Phase 4: Deprecation (Week 7-8)

1. Update documentation to prefer UV scripts
1. Add deprecation notices to bash scripts
1. Provide migration guide for users


**Prerequisites for Deprecation**:

- All CI jobs green using UV scripts for ≥2 weeks
- Zero regression issues reported
- Fallback plan documented and tested
- Bash scripts remain available for emergency rollback for 30 days


### Backward Compatibility

- Keep existing bash scripts during transition
- Add UV script equivalents alongside
- Provide clear documentation on both approaches
- Remove bash scripts only after full adoption

### Rollback Plan

If issues arise during migration:

1. **Immediate Actions**:
   - Revert CI/CD to use bash scripts
   - Document the failure reason
   - Keep UV scripts but mark as experimental

2. **Recovery Criteria**:
   - Fix identified issues
   - Add regression tests
   - Wait 1 additional week before retry

3. **Communication**:
   - Notify team via GitHub issue
   - Update project status in README
   - Post-mortem after resolution

## Best Practices for UV Scripts

### Script Organization

```text
scripts/
├── uv/                    # UV single-file scripts
│   ├── release.py
│   ├── test-zammad.py
│   ├── coverage-report.py
│   └── ...
├── setup.sh              # Keep during transition
└── quality-check.sh      # Keep during transition
```

### Script Standards


1. **Shebang**: Use `#!/usr/bin/env -S uv run --script` for executable scripts (requires GNU coreutils)
1. **Metadata**: Always include inline script metadata
1. **Type Hints**: Use type hints for all functions
1. **Error Handling**: Implement proper error handling with helpful messages
1. **Progress Indication**: Use Rich for progress bars and status updates
1. **Exit Codes**: Return appropriate exit codes for CI/CD integration
1. **Testing**: Coverage targets based on script type:
   - Utility/library scripts: 90% coverage minimum
   - Interactive CLI scripts: 70% coverage (test core logic, not UI)
   - Exclude `if __name__ == "__main__":` blocks from coverage
1. **CI Integration**: Scripts should pass all quality checks (ruff, mypy, bandit)


### Documentation Requirements

Each UV script should include:

1. Module docstring explaining purpose
1. Usage examples in docstring
1. `--help` command with detailed options
1. README section in main project docs

## Conclusion

UV single-file scripts offer significant improvements over the current bash script approach. They provide better developer experience, improved maintainability, and enhanced functionality while maintaining the simplicity of single-file tools. The proposed scripts address current pain points and add new capabilities that would be difficult to implement in bash.

The gradual migration strategy ensures minimal disruption while allowing the team to realize benefits incrementally. Starting with high-value scripts like environment validation and coverage reporting will demonstrate immediate value and build confidence in the approach.
