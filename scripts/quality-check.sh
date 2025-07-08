#!/bin/bash
# Development quality check script following basher83 coding standards

set -euo pipefail

echo "🚀 Running Quality Checks for Zammad MCP..."

# Format code
echo "🔧 Formatting code with ruff..."
uv run ruff format mcp_zammad/ tests/

# Lint code
echo "📝 Linting with ruff..."
uv run ruff check mcp_zammad/ tests/ --fix

# Type checking
echo "🔍 Type checking with mypy..."
uv run mypy mcp_zammad/

# Security checks
echo "🔒 Running security scans..."
echo ""
echo "💡 Tip: You can also use the unified security scanner:"
echo "   ./scripts/uv/security-scan.py"
echo ""

echo "🔒 Security scanning with bandit..."
uv run bandit -r mcp_zammad/ -f json -o bandit-report.json || echo "⚠️ Bandit found issues - check bandit-report.json"

echo "🔍 Security scanning with semgrep..."
uv run semgrep --config=auto --error mcp_zammad/ || echo "⚠️ Semgrep found issues"

echo "🛡️ Dependency vulnerability check with safety..."
uv run safety check --json || echo "⚠️ Safety found vulnerabilities"

echo "🔐 Additional dependency audit with pip-audit..."
uv run pip-audit --format=json --output=pip-audit-report.json || echo "⚠️ pip-audit found vulnerabilities - check pip-audit-report.json"

# Tests
echo "✅ Running tests..."
uv run pytest tests/ --cov=mcp_zammad --cov-report=term-missing

echo "🎉 Quality checks complete!"
echo ""
echo "📊 Reports generated:"
echo "  - bandit-report.json (security issues)"
echo "  - pip-audit-report.json (dependency vulnerabilities)"
echo ""
echo "🚀 Ready for commit!"
