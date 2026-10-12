#!/bin/bash
# Set up a Claude Code cloud session with the toolchain pinned in mise.toml.
#
# Runs `mise run cloud-setup` (locked tools, .venv, prek commit hooks), then
# puts the mise shims first on the session PATH, so that `uv`, `python` and
# `prek` resolve to the pinned versions instead of preinstalled ones (#387).
# Local sessions exit at once; use `mise run setup` there.
set -euo pipefail

[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

export PATH="$HOME/.local/bin:$PATH"
if ! command -v mise >/dev/null 2>&1; then
  echo "session-start: mise is not installed. Add 'curl https://mise.run | sh' to the cloud environment's setup script." >&2
  exit 1
fi

cd "$CLAUDE_PROJECT_DIR"
# Hook stdout becomes session context; keep the install log on stderr.
mise trust --quiet >&2
mise run cloud-setup >&2
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  mise activate bash --shims >> "$CLAUDE_ENV_FILE"
fi
