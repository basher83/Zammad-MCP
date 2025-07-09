---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*), Bash(git log --oneline -5 --no-merges), Task
description: Create git commits following project conventions using parallel analysis agents
---

# Git Commit Helper v2 - Parallel Agent Edition

Create well-structured git commits using parallel agents for analysis and intelligent pre-commit handling.

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

## Execution Strategy

### Phase 0: Pre-flight Check

Run a quick check to identify potential pre-commit hook failures:

- Check if pre-commit is installed: !`which pre-commit || echo "pre-commit not found"`
- Identify high-risk files that might fail hooks

### Phase 1: Parallel Analysis

Deploy parallel agents to analyze different aspects of changes:

**Agent Distribution:**

- Agent 1: Analyze source code changes (`*.py`, `*.js`, `*.ts` files)
- Agent 2: Analyze configuration changes (`*.toml`, `*.yaml`, `*.json`)
- Agent 3: Analyze documentation changes (`*.md`, `*.txt`, README)
- Agent 4: Analyze scripts and CI/CD (`scripts/*`, `.github/*`)

**Agent Task Template:**

```text
Analyze [DOMAIN] changes for git commits.

FILES TO ANALYZE: [list of files]

TASKS:
1. Understand the nature of changes using git diff
1. Group related changes within your domain
1. Propose commit messages following the emoji convention
1. Identify files that might fail pre-commit hooks
1. Note dependencies with other domains

OUTPUT FORMAT:
{
  "domain": "[domain_name]",
  "proposed_commits": [
    {
      "files": ["file1", "file2"],
      "message": "🎯 type(scope): description",
      "rationale": "why these belong together",
      "pre_commit_risk": "low|medium|high",
      "potential_issues": ["list of potential hook failures"]
    }
  ]
}
```

### Phase 2: Commit Planning

Synthesize parallel analyses into a smart commit plan:

1. Merge related changes across domains
1. Order commits by risk (low-risk first)
1. Plan pre-commit failure handling
1. Optimize for atomic, logical commits

### Phase 3: Sequential Execution with Recovery

**For each planned commit:**

1. Stage files using `git add`
1. Attempt commit with message
1. **If pre-commit fails:**
   - Analyze failure output
   - If auto-fixable (ruff, formatting):
     - Accept fixes and restage
     - Retry commit
   - If manual fix needed:
     - Deploy fix agent for specific issue
     - Apply fixes and retry
   - If dependency issue:
     - Alert user and continue with other commits
1. Verify commit success
1. Show updated git status

### Phase 4: Summary

Provide a summary of:

- Successful commits created
- Any pre-commit issues encountered and resolved
- Any issues requiring user intervention

## Pre-commit Hook Handling

**Known hooks in this repository:**

- ruff: Python linting (auto-fixable)
- ruff-format: Python formatting (auto-fixable)
- mypy: Type checking (manual fix)
- bandit: Security analysis (manual fix)
- semgrep: Security patterns (manual fix)
- safety/pip-audit: Dependency checks (requires updates)
- Markdown validators: Format checking

**Recovery strategies:**

- Max 3 attempts per commit
- Isolate problematic files if needed
- Continue with other commits on persistent failures
- Clear reporting of all actions taken

## Your Task

Based on the changes shown above:

1. Deploy parallel analysis agents to understand changes efficiently
1. Create a smart commit plan considering pre-commit risks
1. Execute commits sequentially with intelligent recovery
1. Handle pre-commit failures gracefully
1. Provide clear summary of results

Remember: Each commit should be atomic and logical. The parallel agents help analyze faster, but commits remain sequential to avoid conflicts.

**IMPORTANT**: Do NOT push commits to remote. The user will review all commits before pushing.
