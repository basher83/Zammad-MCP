# UV Scripts

This directory contains UV single-file scripts that provide development and operational tools for the Zammad MCP project.

## Script Execution

These scripts can be executed in several ways:

### Direct Execution (Recommended for GNU/Linux)

```bash
./dev-setup.py
./test-zammad.py
# etc.
```

### Using UV directly (Most Portable)

```bash
uv run --script dev-setup.py
uv run --script test-zammad.py
# etc.
```

## Cross-Platform Considerations

The scripts use the shebang `#!/usr/bin/env -S uv run --script`. The `-S` flag is a GNU coreutils extension that allows passing multiple arguments through env.

### Platform Compatibility

- ✅ **Linux (GNU coreutils)**: Full support
- ❌ **macOS (BSD env)**: No `-S` flag support
- ❌ **Alpine (BusyBox)**: No `-S` flag support
- ❌ **FreeBSD/OpenBSD**: No `-S` flag support

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
