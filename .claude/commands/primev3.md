---
allowed-tools: Bash, Read
description: Load context for a new agent session by analyzing codebase structure and README
---

# Prime

This command loads essential context for a new agent session by examining the codebase structure and reading the project README.

## Instructions

- Provide a concise overview of the project based on the gathered context

## Context

- Extract the essential documentation - what the project is, how to install it, usage examples: !`cat README.md 2>/dev/null | head -100 | grep -E "^(#|-)|.*(install|pip|npm|cargo|Usage:|Getting Started:|Quick Start:|Example:)" | head -40 || (echo "No README. Let me look around..." && ls -la && find . -name "*.py" -o -name "*.js" -o -name "*.go" | head -10)`

- Codebase structure and last 30 days of modified code: !`find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" \) ! -path "./.git/*" ! -path "./node_modules/*" ! -path "./.venv/*" -mtime -30 -exec ls -la {} \; | sort -k6,7 -r | head -20 && echo -e "\n=== STRUCTURE ===" && (command -v tree >/dev/null && tree -L 2 -I '.git|node_modules|.venv|__pycache__' --dirsfirst 2>/dev/null | head -25 || find . -type d ! -path "./.git/*" ! -path "./node_modules/*" ! -path "./.venv/*" ! -path "./__pycache__/*" -print | head -30)`
