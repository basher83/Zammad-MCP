#!/usr/bin/env bash
# Run canonical local validation gates.
set -euo pipefail

mode="${1:-developer}"

run_developer() {
  uv run ruff format --check mcp_zammad tests
  uv run ruff check mcp_zammad tests
  uv run mypy mcp_zammad
  uv run pytest "${@:2}"
}

run_release() {
  run_developer
  uv build
}

case "$mode" in
  developer) run_developer "$@" ;;
  release) run_release ;;
  *) echo "Usage: $0 [developer [pytest args...]|release]" >&2; exit 2 ;;
esac
