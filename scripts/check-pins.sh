#!/usr/bin/env bash
# Check that every tool version comes from mise.toml (the pins gate).
#
# Usage:
#   scripts/check-pins.sh     # run from anywhere inside the repository
#
# Runs as the `version-pins` pre-commit hook and in `scripts/validate.sh`
# (lint, dev, release), so a commit and CI apply the same rules. Each failure
# prints what is wrong, why the rule exists and what to do instead, for
# readers, often agents, that have not read AGENTS.md. Background: #387.
#
# Reads the committed state: the git index for .python-version, and the
# files in the working tree for everything else. Exits 1 on any failure.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

status=0

fail() {
  local what="$1" why="$2" instead="$3"
  printf '❌ pins: %s\n   Why: %s\n   Instead: %s\n' "$what" "$why" "$instead"
  status=1
}

mise_pin() { sed -n "s/^$1 = \"\(.*\)\"$/\1/p" mise.toml; }

# Print the version that mise.lock records for one tool.
lock_version() {
  awk -v table="[[tools.$1]]" '
    $0 == table { found = 1; next }
    found && /^version = / { gsub(/"/, "", $3); print $3; exit }
  ' mise.lock
}

check_python_version_file() {
  [ -z "$(git ls-files .python-version)" ] && return 0
  fail ".python-version is tracked in git." \
    "It is a second Python pin that uv reads whenever UV_PYTHON is unset. It made 'uv run' replace every CI matrix leg's interpreter with the pinned 3.13, so 3.10 to 3.12 went untested (#387)." \
    "Change python in mise.toml [tools]. mise points uv at that Python through UV_PYTHON. Remove the file with 'git rm --cached .python-version'."
}

check_workflows() {
  local found
  found="$(grep -lE 'uses: *(astral-sh/setup-uv|actions/setup-python)@' .github/workflows/*.yml || true)"
  [ -z "$found" ] && return 0
  fail "a workflow installs uv or Python with setup-uv or setup-python: ${found//$'\n'/ }" \
    "CI must install the same tools as local setup, from mise.toml. Separate install steps carry their own version pins, which drift (#387)." \
    "Use jdx/mise-action as in .github/workflows/tests.yml. A job that needs another Python sets UV_PYTHON, as the tests matrix does."
}

check_uv_python_env() {
  grep -qE '^UV_PYTHON = .*tools\.python\.path' mise.toml && return 0
  fail "mise.toml [env] does not set UV_PYTHON to the mise Python." \
    "Without it, uv picks any interpreter that matches requires-python, so local runs stop using the pinned Python." \
    "Keep: UV_PYTHON = { value = \"{{ tools.python.path }}\", tools = true }"
}

check_floating_versions() {
  local floating
  floating="$(awk '/^\[tools\]/ { on = 1; next } /^\[/ { on = 0 } on && /= *"latest"/ { print $1 }' mise.toml)"
  [ -z "$floating" ] && return 0
  fail "mise.toml [tools] uses \"latest\" for: ${floating//$'\n'/ }" \
    "A floating version installs different tools on different days, locally and in CI." \
    "Pin an exact version. Renovate proposes updates for it."
}

check_lockfile() {
  local tool want got
  if [ ! -f mise.lock ]; then
    fail "mise.lock is missing." \
      "jdx/mise-action installs with --locked only when mise.lock exists, so CI would stop verifying checksums." \
      "Run 'mise lock' and commit mise.lock."
    return
  fi
  for tool in python uv; do
    want="$(mise_pin "$tool")"
    got="$(lock_version "$tool")"
    [ "$want" = "$got" ] && continue
    fail "mise.lock records $tool '$got', but mise.toml pins '$want'." \
      "CI installs with --locked and fails on a lockfile that does not match mise.toml." \
      "Run 'mise lock' and commit mise.lock with the mise.toml change."
  done
}

check_hook_pin() {
  local uv="$1" pin
  pin="$(grep -A2 'astral-sh/uv-pre-commit' .pre-commit-config.yaml | sed -n 's/.*# \([0-9.]*\)$/\1/p')"
  [ "$uv" = "$pin" ] && return 0
  fail "the uv-pre-commit hook comment says '$pin', but mise.toml pins uv '$uv'." \
    "The hook is the only copy of the uv pin outside mise.toml, and the comment is the version this gate can read." \
    "Update the hook rev and its version comment together with uv in mise.toml. Renovate groups these updates."
}

main() {
  local uv
  uv="$(mise_pin uv)"
  if [ -z "$uv" ] || [ -z "$(mise_pin python)" ]; then
    fail "cannot read the python and uv pin from mise.toml [tools]." \
      "mise.toml is the only source of tool versions; every other check compares against it." \
      "Keep exact 'python = \"X.Y.Z\"' and 'uv = \"X.Y.Z\"' lines in [tools]."
  else
    check_hook_pin "$uv"
    check_lockfile
  fi
  check_python_version_file
  check_workflows
  check_uv_python_env
  check_floating_versions
  if [ "$status" -ne 0 ]; then
    echo "   Do not weaken or bypass this check to get a commit through. Rules: AGENTS.md \"Version pins and gates\"."
    exit 1
  fi
  echo "📌 pins: python $(mise_pin python) and uv $uv come only from mise.toml and mise.lock"
}

main
