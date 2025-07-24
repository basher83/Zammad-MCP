# Pre-commit Troubleshooting Examples for git_commitv2

## Example 1: Ruff Auto-fix

```bash
# Commit attempt fails with ruff
$ git commit -m "🐛 fix(models): correct validation logic"
ruff.....................................................................Failed
- hook id: ruff
- exit code: 1
- files were modified by this hook

Fixed 2 errors:
  - Removed unused import
  - Fixed line too long

# Recovery: Auto-accept fixes and retry
$ git add -u  # Re-stage the fixed files
$ git commit -m "🐛 fix(models): correct validation logic"
# Success!
```

## Example 2: MyPy Type Error

```bash
# Commit fails with type error
$ git commit -m "🎯 feat(api): add new endpoint"
mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

models.py:45: error: Incompatible return value type (got "str", expected "int")

# Recovery: Deploy fix agent
# Fix Agent analyzes the error and applies type correction
# Then retry commit
```

## Example 3: Multiple Hook Failures

```bash
# Commit fails multiple hooks
$ git commit -m "🔧 refactor(client): improve error handling"
ruff.....................................................................Failed
mypy.....................................................................Failed
bandit...................................................................Failed

# Recovery Strategy:
1. Let ruff auto-fix formatting issues
1. Deploy type fix agent for mypy errors
1. Deploy security fix agent for bandit issues
1. Re-stage all fixes
1. Retry commit
```

## Example 4: Markdown Validation

```bash
# Commit fails custom markdown hook
$ git commit -m "📚 docs: update API documentation"
Block plaintext code fences..............................................Failed
- hook id: no-plaintext-fence
- exit code: 1

README.md:45: ❌ Use ```text instead of ```plaintext

# Recovery: Deploy markdown fix agent
# Agent replaces ```plaintext with ```text
# Retry commit
```

## Pre-commit Fix Agent Templates

### Type Fix Agent

```text
Fix mypy type errors in the following files.

ERRORS:
[paste mypy output]

TASKS:
1. Analyze each type error
1. Determine correct type annotation
1. Apply minimal fix to resolve error
1. Ensure fix doesn't break functionality
```

### Security Fix Agent

```text
Fix security issues identified by bandit/semgrep.

ISSUES:
[paste security scan output]

TASKS:
1. Analyze each security issue
1. Determine appropriate fix
1. Apply secure coding practices
1. Add comments explaining the fix if needed
```

### Markdown Fix Agent

```text
Fix markdown formatting issues.

ISSUES:
[paste markdown validation errors]

TASKS:
1. Fix code fence languages
1. Ensure consistent list numbering
1. Add required blank lines
1. Maintain content integrity
```

## Failure Patterns and Solutions

### Pattern 1: Cascading Fixes

When fixing one issue creates another:

- Track all changes made by fix agents
- Run pre-commit dry-run after fixes
- Have secondary fix agents ready

### Pattern 2: Unfixable Issues

Some issues require human intervention:

- Dependency vulnerabilities (safety/pip-audit)
- Complex type system changes
- Security issues requiring architectural changes

### Pattern 3: Hook Conflicts

When different hooks want conflicting changes:

- Prioritize security over style
- Prioritize functionality over formatting
- Document conflicts for user review

## Best Practices

1. **Group Similar Files**: Files likely to have similar issues should be committed together
1. **Small Commits**: Smaller commits are easier to fix if hooks fail
1. **Test Locally**: Run `pre-commit run --files <files>` before committing
1. **Learn Patterns**: Track which files commonly fail which hooks
1. **Optimize Order**: Commit low-risk files first to build momentum

## Context Management for Fix Agents

When deploying fix agents:

- Provide minimal context (just the files and errors)
- Use focused, single-purpose agents
- Avoid loading entire codebase context
- Chain agents if multiple fixes needed
