# Zammad-MCP Maintainer Workflows

This file curates the useful intent from the previous `.claude/commands` and local hook notes into plugin reference material. It is documentation only; it does not enable hooks or run commands automatically.

## Session Prime

Start a new repo session by reading the project shape before making claims or edits. Use `git ls-files` for tracked structure, then inspect `README.md`, `CHANGELOG.md`, `pyproject.toml`, and the relevant source or test files for the task. Prefer current repository evidence over stale notes.

## Git Status Review

Use `git status`, `git diff`, and `git branch --show-current` to understand the current workspace before committing or reviewing changes. When comparing against the mainline branch, verify that `origin/main` exists and is up to date before relying on `git diff HEAD origin/main`.

## Commit Preparation

Before committing, keep related implementation and tests together, run the repo quality checks that are appropriate for the change, and follow conventional commit style. This duplicates Codex's built-in git workflow guidance, so it is retained here as a repo reminder rather than an active plugin skill.

## Branch Cleanup

Branch cleanup should start with a dry-run inventory: list local branches, remote branches, merged branches, current branch, and recent commit dates. Delete only branches proven merged or explicitly approved for removal. Use remote deletion only when the branch is no longer needed upstream.

## Local Rule Notes

Use `rg` instead of bare `grep` for repository search. Update the changelog with `mise run changelog` or release-specific git-cliff commands rather than hand-editing released changelog sections. The old forced skill-evaluation hook was Claude-specific and intentionally was not migrated into active plugin behavior.
