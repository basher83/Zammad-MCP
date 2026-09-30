---
allowed-tools: TodoWrite, Read, Write, Edit, Grep, Glob, LS, Bash
description: Use PROACTIVELY after completing coding tasks with 3+ modified files to create
  clean, logical commits following conventional commit standards.
---

# Git Commit

This command creates clean, logical commits. It validates the working tree with the pre-commit hooks first. If the hooks fail, fix the reported problems and run the hooks again before you commit. Follow the `Instructions` and run the `Commands`.

## Instructions

- Review the current state of the git repository using the provided commands.
- Run the pre-commit hooks. If a hook fails, fix the problem and run the hooks again until they pass.
- Group the changes into logical units. One commit per concern (for example: a feature, its tests, an unrelated docs fix). Do not mix unrelated changes in one commit.
- Stage each unit explicitly with `git add <paths>`. Do not use `git add -A` or `git add .`.
- Write each commit message in Conventional Commits format: `<type>(<scope>): <summary>` with type in `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`. Keep the summary under 72 characters, imperative mood. Add a body when the why is not obvious.
- Never push unless the user asks.
- Report the commit hashes and one-line summaries when done.

## Commands

- Current Status: !`git status`
- Current diff: !`git diff origin/main...HEAD`
- Current branch: !`git branch --show-current`
- Run Pre-commit Hooks: !`mise run pre-commit-run`
