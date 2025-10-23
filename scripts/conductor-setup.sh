#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Setting up Zammad MCP workspace..."
echo ""

# Check for required tools
echo "🔍 Checking for required tools..."

if ! command -v mise >/dev/null 2>&1; then
    echo "❌ Error: mise is not installed"
    echo "Please install mise: https://mise.jdx.dev/getting-started.html"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "❌ Error: uv is not installed"
    echo "mise will install uv automatically during setup"
fi

echo "✅ Required tools available"
echo ""

# Copy mise.local.toml if it exists in the root repo
if [ -n "${CONDUCTOR_ROOT_PATH:-}" ] && [ -f "$CONDUCTOR_ROOT_PATH/mise.local.toml" ]; then
    echo "📋 Copying mise.local.toml from root repository..."
    cp "$CONDUCTOR_ROOT_PATH/mise.local.toml" mise.local.toml
    echo "✅ mise.local.toml copied"
else
    echo "⚠️  Warning: mise.local.toml not found in root repository"
    echo "You'll need to create mise.local.toml with your Zammad credentials:"
    echo ""
    echo "[env]"
    echo "ZAMMAD_URL = \"https://your-instance.zammad.com/api/v1\""
    echo "ZAMMAD_HTTP_TOKEN = \"your-api-token-here\""
    echo ""
fi

# Run mise setup task
echo "📦 Running mise setup..."
mise run setup

echo ""
echo "✅ Workspace setup complete!"
echo ""
echo "Next steps:"
echo "  1. Ensure mise.local.toml has your Zammad credentials"
echo "  2. Run tests: uv run pytest"
echo "  3. Run quality checks: ./scripts/quality-check.sh"
