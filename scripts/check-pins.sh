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

# Print a failure with its reason and remedy, and mark the run as failed.
fail() {
  local what="$1" why="$2" instead="$3"
  printf '❌ pins: %s\n   Why: %s\n   Instead: %s\n' "$what" "$why" "$instead"
  status=1
}

# Print the exact version string that mise.toml [tools] sets for one tool.
mise_pin() { sed -n "s/^$1 = \"\(.*\)\"$/\1/p" mise.toml; }

# Print "<tool><TAB><version>" for every entry in mise.toml [tools].
tool_entries() {
  awk '
    /^\[tools\]/ { on = 1; next }
    /^\[/ { on = 0 }
    on && /^[^#[:space:]][^=]*=/ {
      value = $0; sub(/^[^=]*= */, "", value); gsub(/"/, "", value)
      print $1 "\t" value
    }
  ' mise.toml
}

# Print the version that mise.lock records for one tool.
lock_version() {
  awk -v table="[[tools.$1]]" '
    $0 == table { found = 1; next }
    found && /^version = / { gsub(/"/, "", $3); print $3; exit }
  ' mise.lock
}

# Fail when .python-version is in the git index.
check_python_version_file() {
  [ -z "$(git ls-files .python-version)" ] && return 0
  fail ".python-version is tracked in git." \
    "It is a second Python pin that uv reads whenever UV_PYTHON is unset. It made 'uv run' replace every CI matrix leg's interpreter with the pinned 3.13, so 3.10 to 3.12 went untested (#387)." \
    "Change python in mise.toml [tools]. mise points uv at that Python through UV_PYTHON. Remove the file with 'git rm --cached .python-version'."
}

# Fail when a workflow installs uv or Python outside mise.
check_workflows() {
  local found
  found="$(grep -rlE --include='*.yml' --include='*.yaml' "uses:[[:space:]]*[\"']?(astral-sh/setup-uv|actions/setup-python)@" .github/workflows 2>/dev/null || true)"
  [ -z "$found" ] && return 0
  fail "a workflow installs uv or Python with setup-uv or setup-python: ${found//$'\n'/ }" \
    "CI must install the same tools as local setup, from mise.toml. Separate install steps carry their own version pins, which drift (#387)." \
    "Use jdx/mise-action as in .github/workflows/tests.yml. A job that needs another Python sets UV_PYTHON, as the tests matrix does."
}

# Fail unless the [env] section of mise.toml points UV_PYTHON at the mise Python.
check_uv_python_env() {
  awk -v want='UV_PYTHON = { value = "{{ tools.python.path }}", tools = true }' '
    /^\[/ { in_env = ($0 == "[env]") }
    in_env && $0 == want { found = 1 }
    END { exit !found }
  ' mise.toml && return 0
  fail "mise.toml [env] does not set UV_PYTHON to the mise Python." \
    "Without it, uv picks any interpreter that matches requires-python, so local runs stop using the pinned Python." \
    "Keep this exact line in [env]: UV_PYTHON = { value = \"{{ tools.python.path }}\", tools = true }"
}

# Fail when a [tools] entry is not an exact X.Y.Z version.
check_exact_versions() {
  local loose
  loose="$(tool_entries | awk -F '\t' '$2 !~ /^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$/ { print $1 "=" $2 }')"
  [ -z "$loose" ] && return 0
  fail "mise.toml [tools] has versions that are not exact: ${loose//$'\n'/ }" \
    "\"latest\" or a prefix such as \"2\" resolves to different releases on different days, locally and in CI." \
    "Pin an exact X.Y.Z version. Renovate proposes updates for it."
}

# Fail when mise.lock is missing or does not record every [tools] version.
check_lockfile() {
  local tool want got
  if [ ! -f mise.lock ]; then
    fail "mise.lock is missing." \
      "jdx/mise-action installs with --locked only when mise.lock exists, so CI would stop verifying checksums." \
      "Run 'mise lock' and commit mise.lock."
    return
  fi
  while IFS=$'\t' read -r tool want; do
    got="$(lock_version "$tool")"
    [ "$want" = "$got" ] && continue
    fail "mise.lock records $tool '${got:-nothing}', but mise.toml pins '$want'." \
      "Installs with --locked (CI, and 'mise install --locked' locally) fail on a lockfile that does not match mise.toml." \
      "Run 'mise lock' and commit mise.lock with the mise.toml change."
  done < <(tool_entries)
}

# Fail when the uv-pre-commit hook is missing or its version comment differs from mise.toml.
check_hook_pin() {
  local uv="$1" pin
  if ! grep -q 'astral-sh/uv-pre-commit' .pre-commit-config.yaml; then
    fail "the uv-pre-commit hook is missing from .pre-commit-config.yaml." \
      "Its uv-sync hook keeps .venv in step with uv.lock, and its version comment is the only copy of the uv pin outside mise.toml." \
      "Restore the astral-sh/uv-pre-commit entry with a rev and a '# <uv version>' comment that matches mise.toml."
    return
  fi
  pin="$(grep -A2 'astral-sh/uv-pre-commit' .pre-commit-config.yaml | sed -n 's/.*# \([0-9.]*\)$/\1/p')"
  [ "$uv" = "$pin" ] && return 0
  fail "the uv-pre-commit hook comment says '$pin', but mise.toml pins uv '$uv'." \
    "The hook is the only copy of the uv pin outside mise.toml, and the comment is the version this gate can read." \
    "Update the hook rev and its version comment together with uv in mise.toml. Renovate groups these updates."
}

# Run every check, then print the shared reminder and exit 1 on any failure.
main() {
  local uv
  uv="$(mise_pin uv)"
  if [ -z "$uv" ] || [ -z "$(mise_pin python)" ]; then
    fail "cannot read the python and uv pin from mise.toml [tools]." \
      "mise.toml is the only source of tool versions; every other check compares against it." \
      "Keep exact 'python = \"X.Y.Z\"' and 'uv = \"X.Y.Z\"' lines in [tools]."
  else
    check_hook_pin "$uv"
  fi
  check_lockfile
  check_python_version_file
  check_workflows
  check_uv_python_env
  check_exact_versions
  if [ "$status" -ne 0 ]; then
    echo "   Do not weaken or bypass this check to get a commit through. Rules: AGENTS.md \"Version pins and gates\"."
    exit 1
  fi
  echo "📌 pins: python $(mise_pin python) and uv $uv come only from mise.toml and mise.lock"
}

main
