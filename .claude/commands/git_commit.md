---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*), Bash(git log:*)
description: Create git commits following project conventions without Claude Code signature
---

# Git Commit Helper

Create well-structured git commits for modified files following the project's commit conventions.

## Important Instructions

1. **DO NOT** include the Claude Code signature (🤖 Generated with [Claude Code]) in commit messages
1. **DO NOT** include "Co-Authored-By: Claude" in commits
1. **DO NOT** push to remote - the user will review and push after all commits are created
1. Follow the commit conventions defined in @.gitmessage
1. Group related changes into logical commits
1. Use clear, imperative mood in commit messages

## Git Context

- Current Status: !`git status --porcelain`
- Staged Changes: !`git diff --cached --stat && echo "---" && git diff --cached | head -500`
- Unstaged Changes: !`git diff --stat && echo "---" && git diff | head -500`
- Current Branch: !`git branch --show-current`
- Recent Commits: !`git log --oneline -5 --no-merges`

## Commit Convention Template

@.gitmessage

## Your Task

Based on the changes shown above:

1. Analyze all modified files to understand the changes
1. Group related changes together logically
1. Create commits using the emoji-based format from .gitmessage:
   - Format: `<emoji> <type>(<scope>): <description>`
   - Example: `🎯 feat(auth): add multi-factor authentication`
1. Stage appropriate files for each commit using `git add`
1. Create commits with descriptive messages (NO Claude Code signature)
1. After each commit, show the updated git status

Remember: Each commit should represent a single logical change or feature.

**IMPORTANT**: Do NOT push commits to remote. The user will review all commits before pushing.
