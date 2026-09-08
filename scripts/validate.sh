#!/usr/bin/env bash
# Canonical non-mutating validation gates for Zammad MCP.
#
# Usage:
#   scripts/validate.sh lint          # format check + ruff + mypy (parallel)
#   scripts/validate.sh test          # affected tests (diff vs base) or full suite
#   scripts/validate.sh dev           # lint + affected tests (fast developer loop)
#   scripts/validate.sh release       # lint + full coverage suite + package build
#
# Rules (format, lint, types, coverage floor) live in pyproject.toml; this
# script only decides *which* gates run and in what order. CI workflows call
# the same subcommands so local and GitHub results match.
#
# Affected-test fallback: when git history or a base ref is unavailable, or
# when shared files (pyproject.toml, uv.lock, tests/conftest.py) change, the
# full suite runs. This is deterministic and errs toward more coverage.
#
# Caching: ruff and mypy use their on-disk caches (.ruff_cache, .mypy_cache);
# uv resolves from the frozen uv.lock. Set VALIDATE_NO_CACHE=1 to disable.

set -euo pipefail
cd "$(dirname "$0")/.."

BASE_REF="${VALIDATE_BASE_REF:-origin/main}"
SRC_DIRS=(mcp_zammad tests)
CACHE_FLAG=()
if [ "${VALIDATE_NO_CACHE:-0}" = "1" ]; then
  CACHE_FLAG=(--no-cache)
fi

run_lint() {
  echo "🔎 lint: ruff format --check, ruff check, mypy (parallel)"
  local pids=() names=(format ruff mypy) status=0
  uv run ruff format --check "${SRC_DIRS[@]}" "${CACHE_FLAG[@]}" & pids+=($!)
  uv run ruff check "${SRC_DIRS[@]}" "${CACHE_FLAG[@]}" & pids+=($!)
  uv run mypy mcp_zammad & pids+=($!)
  for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then
      echo "❌ ${names[$i]} failed"
      status=1
    fi
  done
  return "$status"
}

changed_files() {
  git diff --name-only "$BASE_REF"...HEAD 2>/dev/null || return 1
  git diff --name-only HEAD 2>/dev/null
  git ls-files --others --exclude-standard
}

affected_tests() {
  local files tests=()
  if ! files="$(changed_files | sort -u)"; then
    echo "tests"
    return
  fi
  [ -z "$files" ] && { echo ""; return; }
  if grep -qE '^(pyproject\.toml|uv\.lock|tests/conftest\.py)$' <<<"$files"; then
    echo "tests"
    return
  fi
  while IFS= read -r f; do
    case "$f" in
      tests/test_*.py) tests+=("$f") ;;
      mcp_zammad/*.py)
        local mod; mod="$(basename "$f" .py)"
        tests+=(tests/test_"$mod"*.py tests/test_server.py) ;;
    esac
  done <<<"$files"
  [ "${#tests[@]}" -eq 0 ] && { echo ""; return; }
  printf '%s\n' "${tests[@]}" | sort -u | while IFS= read -r t; do
    compgen -G "$t" || true
  done | sort -u | tr '\n' ' '
}

run_affected_tests() {
  local targets
  targets="$(affected_tests)"
  if [ -z "$targets" ]; then
    echo "✅ test: no affected tests for changed files"
    return
  fi
  echo "🧪 test (affected vs $BASE_REF): $targets"
  # shellcheck disable=SC2086
  uv run pytest -q -p no:cacheprovider $targets
}

run_full_tests() {
  echo "🧪 test (full suite with coverage floor from pyproject.toml)"
  uv run pytest tests/ -q --cov=mcp_zammad --cov-report=term-missing --no-cov-on-fail
}

run_build() {
  echo "📦 build: uv build"
  rm -rf dist
  uv build --quiet
}

case "${1:-dev}" in
  lint) run_lint ;;
  test) run_affected_tests ;;
  dev) run_lint && run_affected_tests ;;
  release) run_lint && run_full_tests && run_build ;;
  *) echo "usage: $0 {lint|test|dev|release}" >&2; exit 2 ;;
esac
echo "✅ validate ${1:-dev}: passed"
