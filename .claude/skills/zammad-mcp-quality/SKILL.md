---
name: zammad-mcp-quality
description: Quality assurance and CodeRabbit learning system for Zammad MCP development. Use when creating PRs, implementing MCP tools, adding pagination, handling errors, or addressing CodeRabbit feedback. Provides checklists, pattern guides, and accumulated project learnings to prevent recurring issues.
---

# Zammad MCP Quality Guardian

## Purpose

Ensure consistent, high-quality contributions to the Zammad MCP project by:

1. **Preventing recurring issues** flagged by CodeRabbit
2. **Providing actionable checklists** for self-review
3. **Capturing project learnings** in accessible references
4. **Systematic improvement** through feedback loop integration

## When to Use This Skill

Trigger this skill when:

- **Before creating a PR** - Self-review with checklist
- **Implementing MCP tools** - Follow established patterns
- **Adding pagination** - Use correct metadata structure
- **Handling errors** - Create actionable messages
- **Addressing CodeRabbit feedback** - Learn patterns, not just fix issues
- **Onboarding to project** - Understand quality standards
- **Monthly review** - Update learnings from recent PRs

## Workflow

### 1. Pre-Development (Optional)

When starting a new feature, review relevant references:

**For pagination features:**
→ Read [pagination-patterns.md](./references/pagination-patterns.md)

**For error handling:**
→ Read [error-handling-guide.md](./references/error-handling-guide.md)

**For type-heavy code:**
→ Read [type-annotation-standards.md](./references/type-annotation-standards.md)

### 2. During Development

Keep patterns in mind while coding:

- Use Python 3.10+ type syntax
- Provide actionable error messages
- Structure pagination metadata correctly
- Follow naming conventions (no shadowing)

### 3. Pre-PR Self-Review (CRITICAL)

**ALWAYS run through the checklist before creating a PR:**

→ Open [pre-pr-checklist.md](./references/pre-pr-checklist.md)

This takes 5-10 minutes but reduces review iterations by 60-70%.

**Quick quality check:**

```bash
# From project root
./scripts/quality-check.sh && uv run pytest --cov=mcp_zammad
```

### 4. After CodeRabbit Review

**When CodeRabbit comments on your PR:**

1. **Fix the immediate issue** in your code
2. **Understand the pattern** - don't just copy-paste
3. **Check if pattern is documented** in this skill
   - If yes: Review reference to avoid future occurrences
   - If no: Consider if pattern should be added
4. **Search codebase** for similar instances
5. **Update learnings** if pattern recurs (see Update Process below)

### 5. Monthly Review (Maintainers)

**Process for keeping skill current:**

1. Review last 10 merged PRs
2. Note recurring CodeRabbit feedback
3. Update [coderabbit-learnings.md](./references/coderabbit-learnings.md)
4. Update [pre-pr-checklist.md](./references/pre-pr-checklist.md) if needed
5. Refine reference guides based on new patterns

**Estimated time:** 30 minutes/month

---

## Reference Documents

### 📊 Start Here

**[pre-pr-checklist.md](./references/pre-pr-checklist.md)**
Quick self-review checklist. Use before every PR.

**[coderabbit-learnings.md](./references/coderabbit-learnings.md)**
Consolidated feedback from PR reviews. Living knowledge base.

### 📚 Deep Dive Guides

**[pagination-patterns.md](./references/pagination-patterns.md)**
Complete guide to pagination in MCP servers:

- Required metadata fields
- Common mistakes & fixes
- JSON truncation that preserves validity
- Examples from codebase

**[error-handling-guide.md](./references/error-handling-guide.md)**
Actionable error message patterns:

- Error message template
- HTTP status code mapping
- ID vs number confusion (Issue #99)
- Configuration errors
- Anti-patterns to avoid

**[type-annotation-standards.md](./references/type-annotation-standards.md)**
Python 3.10+ type annotation guide:

- Modern vs legacy syntax
- Parameter shadowing fixes
- Pydantic model types
- Type narrowing with `cast()`
- MyPy configuration

---

## Scripts

### extract_feedback.py (Future)

Stub for automating CodeRabbit feedback extraction:

```bash
# Future usage
python scripts/extract_feedback.py --prs 10 --output references/coderabbit-learnings.md
```

**Status:** Planned for Phase 3 automation
**See:** scripts/extract_feedback.py for stub

---

## Usage Examples

### Example 1: Before Creating a PR

```text
User: "I'm ready to create a PR for the new search filter feature"

Claude: Let me help you with pre-PR review using the Zammad MCP Quality skill.

*Reviews pre-pr-checklist.md*

I'll check your code against the quality checklist:

1. Type Annotations ✓
   - All functions have return types
   - Using modern list[str] syntax
   - No parameter shadowing

2. Pagination ⚠️
   - Found: response["total"] = len(items)
   - Should be: total from API or None
   - See pagination-patterns.md line 45

3. Error Handling ✓
   - Messages are actionable
   - Using proper exception chaining

Let me fix the pagination issue before you create the PR...
```

### Example 2: Implementing New Tool

```text
User: "Add a new tool for managing ticket watchers"

Claude: I'll implement following Zammad MCP patterns from the quality skill.

*Checks coderabbit-learnings.md for relevant patterns*

Key patterns to follow:
1. Use Pydantic model for input (TicketSearchParams pattern)
2. Support ResponseFormat.JSON and .MARKDOWN
3. Clear docstring explaining ID vs number (from Issue #99 learnings)
4. Proper error handling with actionable messages

*Reviews error-handling-guide.md for message templates*

Implementing tool with these quality standards...
```

### Example 3: Addressing CodeRabbit Feedback

```text
CodeRabbit: "The 'total' field is set to page count, not true total across all pages."

Claude: Let me check the pagination-patterns.md guide...

*Reviews pagination-patterns.md section on "Common Mistakes"*

I see - this is a known pattern. The guide shows:

❌ Wrong: response["total"] = len(tickets)
✅ Correct: response["total"] = total_from_api  # or None if unknown

Let me fix this and also check for similar instances in the codebase...

*Searches for pattern in other pagination functions*

Found 3 other locations with same issue. Fixing all...

*Updates coderabbit-learnings.md with occurrence count*
```

---

## Quality Metrics

Track these over time to measure skill effectiveness:

### Leading Indicators

- CodeRabbit comments per PR (Target: < 5)
- Checklist completion rate (Target: 100%)
- Pre-commit check pass rate (Target: > 95%)

### Lagging Indicators

- Issue recurrence rate (same pattern 2+ PRs)
- Time to first approval (Target: < 1 hour)
- Test coverage (Target: > 90%)

---

## Skill Maintenance

### Update Triggers

Update this skill when:

- CodeRabbit pattern appears 2+ times
- Major PR with significant feedback
- New MCP best practice discovered
- Project architecture changes
- Monthly review cycle

### Update Process

1. **Identify pattern** from CodeRabbit feedback
2. **Categorize** (pagination, errors, types, etc.)
3. **Document** in appropriate reference guide
4. **Add to checklist** if high-frequency
5. **Test pattern** with codebase examples
6. **Validate** in next PR

### Contributors

When updating references:

- Use imperative form (not second person)
- Include code examples (both good and bad)
- Link to source PRs/issues
- Add to relevant checklist items
- Keep `coderabbit-learnings.md` as index

---

## Integration with Other Documentation

This skill **complements** existing docs:

**CLAUDE.md** - Project context for Claude Code
→ Focuses on architecture, development rules
→ Quality skill adds CodeRabbit-specific patterns

**.github/copilot-instructions.md** - GitHub Copilot guidance
→ Focuses on code generation patterns
→ Quality skill adds review/validation patterns

**.coderabbit.yaml** - CodeRabbit configuration
→ Focuses on tool settings and path instructions
→ Quality skill captures learnings from reviews

**mcp-builder skill** - Generic MCP development
→ Focuses on MCP protocol and general patterns
→ Quality skill adds Zammad-specific learnings

---

## Success Stories

**Expected outcomes after skill adoption:**

**Week 1:**

- 60-70% reduction in common CodeRabbit comments
- Faster PR reviews (fewer iterations)
- Developers report increased confidence

**Month 1:**

- Comprehensive reference guides for all major patterns
- Self-documenting knowledge base
- Measurable reduction in repeated feedback

**Month 3+:**

- Self-improving system with periodic updates
- New contributor onboarding resource
- Foundation for automation (Phase 3)

---

## Troubleshooting

**Q: Checklist is too long, takes too much time**
A: Focus on sections relevant to your changes. Not every item applies to every PR.

**Q: Found a pattern not documented here**
A: Great! Document it in coderabbit-learnings.md or open an issue to add it.

**Q: CodeRabbit still commenting despite following checklist**
A: Skill evolves with project. Update references based on new feedback.

**Q: How do I know which reference to read?**
A: Start with pre-pr-checklist.md - it links to detailed guides as needed.

---

## Future Enhancements (Phase 3)

Planned automation:

- `extract_feedback.py` - Parse CodeRabbit comments from PRs
- Semi-automated skill updates from PR feedback
- CI/CD integration for pre-commit validation
- Metrics dashboard tracking improvement
- Auto-generate monthly learning summaries

**Status:** Designed in Phase 2, implementation pending

---

## Related Skills

- **mcp-builder** - Generic MCP server development guidance
- **skill-creator** - Creating and maintaining skills

---

## Feedback

**Skill working well?** Great! Keep using the checklist.

**Found issues or improvements?** Update the skill! It's designed to evolve.

**Have questions?** Check existing references or ask in PR discussions.

**Monthly reviews** ensure skill stays current and useful.

---

*This skill is part of a systematic quality improvement system. By using it consistently, you're helping the project learn and improve over time.*
