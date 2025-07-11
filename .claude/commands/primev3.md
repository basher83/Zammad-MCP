---
allowed-tools: Bash, Read
description: Load context for a new agent session by analyzing codebase structure and README
---

# Prime

This command loads essential context for a new agent session by examining the codebase structure and reading the project README.

## Instructions

- Provide a concise overview of the project based on the gathered context

## Context

- Extract the essential documentation - what the project is, how to install it, usage examples:
  !`cat README.md 2>/dev/null | head -100 | rg "^(#|-)|.*(install|pip|npm|cargo|Usage:|Getting Started:|Quick Start:|Example:)" | head -40 || (echo "No README. Let me look around..." && ls -la && fd -e py -e js -e go | head -10)`

- Codebase structure and last 30 days of modified code:
  !`fd -e py -e js -e ts -e go -e rs -t f --changed-within 30d --exec stat -c '%Y %s %n' {} \; | sort -rn | head -20 | while read -r timestamp size path; do printf '%s %12s %s\n' "$(date -d @$timestamp '+%Y-%m-%d %H:%M')" "$size" "$path"; done && echo -e "\n=== STRUCTURE ===" && (command -v tree >/dev/null && tree -L 2 -I '.git|node_modules|.venv|__pycache__' --dirsfirst 2>/dev/null | head -25 || fd -t d -d 2 | head -30)`
