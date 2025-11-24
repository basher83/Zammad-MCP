---
name: protect-changelog
enabled: true
event: file
action: block
pattern: CHANGELOG\.md$
---

🚫 **Direct CHANGELOG.md edits are blocked**

This project uses git-cliff for changelog management.

**Use these commands instead:**

```bash
# Update unreleased section:
mise run changelog

# Prepare a release:
mise run changelog-bump X.Y.Z

# Preview unreleased changes:
git-cliff --unreleased
```

**Why this matters:**
- Maintains consistent changelog formatting
- Auto-generates entries from conventional commits
- Prevents merge conflicts in shared files

See CLAUDE.md for details on changelog management.
