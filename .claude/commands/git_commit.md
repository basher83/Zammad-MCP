---
allowed-tools: TodoWrite, Read, Write, Edit, Grep, Glob, LS, Bash
description: Use PROACTIVELY after completing coding tasks with 3+ modified files to create
  clean, logical commits following conventional commit standards.
---

# Git Commit

This command serves as a git workflow orchestrator to create clean, logical commits while addressing any code quality issues. Follow the `Instructions` and run the `Commands` to execute pre-commit hooks and invoke the commit-craft agent for commit creation.

## Instructions

- Review the current state of the git repository using the provided commands.
- Execute pre-commit hooks and fix any issues in the codebase.
- Invoke the commit-craft agent (@agent-commit-craft) to create clean, logical
  commits for all changes in the repository.

## Commands

- Current Status: !`git status`
- Current diff: !`git diff HEAD origin/main`
- Current branch: !`git branch --show-current`
- Run Pre-commit Hooks: !`mise run pre-commit-run`
- Commit Craft Agent: @agent-commit-craft
