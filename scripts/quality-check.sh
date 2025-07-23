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
echo "   uv run scripts/uv/security-scan.py"
echo ""

echo "🔒 Security scanning with bandit..."
# Only fail on HIGH/CRITICAL issues (--severity-level HIGH)
if uv run bandit -r mcp_zammad/ --severity-level high -f json -o bandit-report.json; then
    echo "✅ Bandit: No HIGH/CRITICAL security issues found"
else
    echo "❌ Bandit: HIGH/CRITICAL security issues found - check bandit-report.json"
    exit 1
fi

echo "🔍 Security scanning with semgrep..."
uv run semgrep --config=auto --error mcp_zammad/ || echo "⚠️ Semgrep found issues"

echo "🔐 Dependency audit with pip-audit..."
uv run pip-audit --format=json --output=pip-audit-report.json || echo "⚠️ pip-audit found vulnerabilities - check pip-audit-report.json"

# Tests
echo "✅ Running tests..."
uv run pytest tests/ \
  --cov=mcp_zammad \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-report=html:htmlcov \
  --cov-fail-under=90 \
  --no-cov-on-fail

echo "🎉 Quality checks complete!"
echo ""
echo "📊 Reports generated:"
echo "  - bandit-report.json (security issues)"
echo "  - pip-audit-report.json (dependency vulnerabilities)"
echo "  - htmlcov/index.html (HTML coverage report)"
echo "  - coverage.xml (test coverage for Codacy)"
echo ""
echo "🚀 Ready for commit!"
