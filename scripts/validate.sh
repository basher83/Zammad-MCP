#!/usr/bin/env bash
# Canonical non-mutating validation gates for Zammad MCP.
#
# Usage:
#   scripts/validate.sh lint          # version pins + format check + ruff + mypy (parallel)
#   scripts/validate.sh test          # affected tests (diff vs base) or full suite
#   scripts/validate.sh dev           # lint + affected tests (fast developer loop)
#   scripts/validate.sh release       # lint + full coverage suite + package build
#
# Rules (format, lint, types, coverage floor) live in pyproject.toml, and
# tool versions live in mise.toml; this
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

# Version pins: mise.toml is the source of truth. uv and setup-python read
# .python-version; setup-uv steps and the uv-pre-commit hook pin uv separately.
mise_pin() { sed -n "s/^$1 = \"\(.*\)\"$/\1/p" mise.toml; }

# Print "<workflow>:<job> <version>" for every astral-sh/setup-uv step, or
# MISSING when the step has no explicit `version` input.
setup_uv_versions() {
  uv run --frozen python - .github/workflows/*.yml <<'PY'
import sys
from pathlib import Path

import yaml

jobs = [(path, name, job) for path in sys.argv[1:]
        for name, job in (yaml.safe_load(Path(path).read_text()).get("jobs") or {}).items()]
steps = [(f"{path}:{name}", step) for path, name, job in jobs for step in job.get("steps") or []]
for label, step in steps:
    if not str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
        continue
    version = (step.get("with") or {}).get("version")
    print(label, "MISSING" if version is None else version)
PY
}

check_pin() {
  local label="$1" want="$2" got="$3"
  [ "$want" = "$got" ] && return 0
  echo "❌ pins: $label is '$got', but mise.toml pins '$want'"
  return 1
}

run_pins() {
  local py uv pin steps step status=0
  py="$(mise_pin python)"
  uv="$(mise_pin uv)"
  if [ -z "$py" ] || [ -z "$uv" ]; then
    echo "❌ pins: cannot read the python and uv pins from mise.toml [tools]"
    return 1
  fi
  check_pin .python-version "$py" "$(tr -d '[:space:]' < .python-version)" || status=1
  pin="$(grep -A2 'astral-sh/uv-pre-commit' .pre-commit-config.yaml | sed -n 's/.*# \([0-9.]*\)$/\1/p')"
  check_pin "the uv-pre-commit hook" "$uv" "$pin" || status=1
  if ! steps="$(setup_uv_versions)"; then
    echo "❌ pins: cannot parse the setup-uv steps in .github/workflows"
    return 1
  fi
  while read -r step pin; do
    [ -n "$step" ] && { check_pin "setup-uv in $step" "$uv" "$pin" || status=1; }
  done <<<"$steps"
  [ "$status" -eq 0 ] && echo "📌 pins: Python $py and uv $uv match mise.toml"
  return "$status"
}

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
      tests/test_*.py | tests/*/test_*.py) tests+=("$f") ;;
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

# Each gate runs as a plain statement so `set -e` aborts on the first failure.
# (`a && b` lists are exempt from errexit and would print a false "passed".)
case "${1:-dev}" in
  lint) run_pins; run_lint ;;
  test) run_affected_tests ;;
  dev) run_pins; run_lint; run_affected_tests ;;
  release) run_pins; run_lint; run_full_tests; run_build ;;
  *) echo "usage: $0 {lint|test|dev|release}" >&2; exit 2 ;;
esac
echo "✅ validate ${1:-dev}: passed"
