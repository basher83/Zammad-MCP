---
name: use-rg-not-grep
enabled: true
event: bash
action: warn
pattern: \bgrep\s+
---

⚠️ Use `rg` instead of `grep`

This project requires ripgrep (`rg`) for searching.

**Why rg is preferred:**
- Faster performance
- Respects .gitignore by default
- Better regex support
- Consistent with project standards

**Example:**

```bash
# Instead of:
grep -r "pattern" .

# Use:
rg "pattern"
```

See CLAUDE.md for project conventions.
