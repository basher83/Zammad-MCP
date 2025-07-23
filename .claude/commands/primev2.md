---
allowed-tools: Bash, Read, Grep, Glob
description: Prime the agent with codebase context using activity-first analysis
---

# Prime v2

This command loads essential context by analyzing what's actively being developed then understanding structure.

## Instructions

Phase 1 - Activity Analysis:

**You MUST run all commands in the Context section below before proceeding.**

- Identify recently modified files to understand what's actively being worked on
- Detect the tech stack and dependencies
- Find entry points and main files
- Check for available scripts and commands

Phase 2 - Structure Analysis:

- Understand the codebase organization with git-aware tree view
- Read key documentation
- Provide a concise, actionable overview

## Context

### 🔥 Recent Activity (What's Alive)

Recent modifications showing active development: !`fd --type f --exclude .git --exclude node_modules --exclude .venv --exclude __pycache__ --exclude target --exclude dist | head -80 | xargs ls -laht 2>/dev/null | head -40`

### 📚 Tech Stack Detection

Package files and dependencies: !`ls -1 *.{json,toml,xml,gradle,rb,txt,lock,mod,sum} 2>/dev/null | rg -i "package|pyproject|Cargo|go\\.mod|pom|Gemfile|requirements|composer|mix\\.exs" | head -10`

### 🚀 Entry Points

Main application files: !`fd -t f -d 3 "(main|index|app|__main__|server|start|run)\\.(py|js|ts|go|rs|java|rb|ex|php)" --exclude node_modules --exclude .venv | head -10`

### 🛠️ Available Commands

Package scripts: !`(rg '"scripts"' package.json -A 20 2>/dev/null | rg '^\s+"[^"]+":' | head -10) || (rg "\\[tool\\.poetry\\.scripts\\]|\\[project\\.scripts\\]" pyproject.toml -A 10 2>/dev/null) || (rg "^[a-z-]+:" Makefile 2>/dev/null | head -10) || echo "No obvious command definitions found"`

### 📂 Project Structure

Git-aware tree with modifications: !`eza -la --tree --git --git-ignore --icons --sort=modified --level=2 --no-user --no-permissions`

### 📊 Quick Stats

File counts by type: !`fd -t f --exclude .git --exclude node_modules --exclude .venv | rg -o "\\.[^.]+$" | sort | uniq -c | sort -rn | head -10`

### 📖 Documentation

- Project README: @README.md
- Architecture details: @ARCHITECTURE.md  
- Recent changes: @CHANGELOG.md

### 🔍 Additional Context

- Git remote info: !`git remote -v 2>/dev/null | head -2`
- Recent commits: !`git log --oneline -10 2>/dev/null`
