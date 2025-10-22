# CodeRabbit Learnings - Consolidated Feedback

## Overview

This document consolidates recurring feedback from CodeRabbit reviews across multiple PRs. It serves as a living knowledge base that evolves with the project.

**Last Updated:** 2025-10-22
**Source PRs:** #97, #101, #96, #99 (issues), and ongoing reviews

---

## 🔄 Recurring Patterns

### 1. Pagination Metadata Issues

**Frequency:** High (appeared in PRs #97, multiple reviews)
**Severity:** Medium (breaks agent functionality)

**Problem:**
- `total` field set to page count instead of true total
- `has_more` heuristic unreliable
- JSON truncation breaks validity

**Solution:**
See [pagination-patterns.md](./pagination-patterns.md) for complete guide.

**Quick Fix:**
```python
response = {
    "items": [...],
    "total": total_from_api,  # NOT len(items)!
    "has_more": (page * per_page < total) if total else (len(items) == per_page)
}
```

**CodeRabbit Quote (PR #97):**
> "The `'total'` field is set to the page item count (`len(tickets)`), not the total matching results across all pages. This breaks the pagination contract."

---

### 2. Type Annotation Legacy Syntax

**Frequency:** Medium (appears in new code, external contributions)
**Severity:** Low (style/consistency issue)

**Problem:**
- Using `List[str]` instead of `list[str]`
- Using `Optional[T]` instead of `T | None`
- Using `Union[A, B]` instead of `A | B`

**Solution:**
```python
# ✅ Modern (Python 3.10+)
items: list[str]
value: str | None
result: int | str

# ❌ Legacy (pre-3.10)
items: List[str]
value: Optional[str]
result: Union[int, str]
```

**CodeRabbit Feedback Pattern:**
> "Use Python 3.10+ syntax: `list[str]` not `List[str]`"

**Auto-Fix:** Ruff can auto-fix many of these with `--fix`

---

### 3. Parameter Shadowing

**Frequency:** Medium (especially with `type` parameter)
**Severity:** Low (but reduces code clarity)

**Problem:**
Parameter names shadow built-ins or type names.

**Common violations:**
- `type` (built-in) → use `article_type`, `resource_type`
- `id` (built-in) → use `ticket_id`, `user_id`
- `format` (built-in) → use `response_format`

**Solution:**
```python
# ❌ BAD
def create_article(type: str, id: int):
    ...

# ✅ GOOD
def create_article(article_type: str, ticket_id: int):
    ...
```

---

### 4. Character Limit Not Configurable

**Frequency:** Low (PR #97)
**Severity:** Low (deployment flexibility)

**Problem:**
Hard-coded `CHARACTER_LIMIT = 25000` requires code changes for different deployments.

**Solution:**
```python
CHARACTER_LIMIT = int(os.getenv("ZAMMAD_MCP_CHARACTER_LIMIT", "25000"))
```

**Status:** ✅ Implemented in PR #97

---

### 5. Bare Exception Catching

**Frequency:** Medium
**Severity:** Medium (can hide bugs)

**Problem:**
Catching `Exception` without specificity or re-raising.

**CodeRabbit Pattern:**
> "Do not catch blind exception: `Exception` (BLE001)"

**Acceptable Usage:**
```python
# ✅ GOOD: Catch, handle, re-raise
try:
    result = api_call()
except Exception as e:
    if "specific_pattern" in str(e):
        raise ValueError("Helpful message") from e
    raise  # Re-raise if not handled

# ✅ GOOD: Specific exceptions
try:
    result = api_call()
except (ValueError, KeyError, requests.HTTPError) as e:
    handle_error(e)

# ❌ BAD: Silent catching
try:
    result = api_call()
except Exception:
    pass  # Silently ignores errors!
```

---

### 6. Cyclomatic Complexity

**Frequency:** Low (appears in large functions)
**Severity:** Low (maintainability)

**Problem:**
Functions with high cyclomatic complexity (> 8-10) are hard to maintain and test.

**CodeRabbit Warnings:**
- `_handle_api_error`: complexity 10
- `_setup_ticket_tools`: complexity 24

**Solution:**
- Extract error-specific handlers into separate functions
- Break large setup methods into smaller helpers
- Use dictionaries/mappings instead of long if/elif chains

**Example Refactor:**
```python
# ❌ High complexity
def _handle_api_error(e, context):
    if "404" in str(e):
        return "Not found..."
    elif "403" in str(e):
        return "Permission denied..."
    elif "401" in str(e):
        return "Auth failed..."
    elif "timeout" in str(e):
        return "Timeout..."
    # ... 10 more conditions

# ✅ Lower complexity
ERROR_HANDLERS = {
    "404": lambda ctx: f"Not found during {ctx}...",
    "403": lambda ctx: f"Permission denied for {ctx}...",
    ...
}

def _handle_api_error(e, context):
    error_msg = str(e).lower()
    for pattern, handler in ERROR_HANDLERS.items():
        if pattern in error_msg:
            return handler(context)
    return f"Error during {context}: {e}"
```

---

### 7. Ruff: Unused `noqa` Directives

**Frequency:** Low
**Severity:** Very Low (cleanup)

**Problem:**
`# noqa` comments for disabled linting rules.

**Solution:**
Remove unused `noqa` or update to correct error code.

```python
# ❌ Unused
def long_function():  # noqa: PLR0915
    ...  # Function is actually short

# ✅ Remove or fix
def long_function():
    ...
```

---

## 📚 CodeRabbit Learnings Feature

CodeRabbit has a "Learnings" feature that tracks project-specific patterns:

**Current Learnings (from .coderabbit.yaml reviews):**

1. **2025-07-24:** "Use FastMCP framework for MCP server implementation"
   - Applies to: `mcp_zammad/**/*.py`
   - Source: .github/copilot-instructions.md

2. **2025-10-21:** "Define MCP prompts in server.py using the mcp.prompt() decorator"
   - Applies to: `mcp_zammad/server.py`
   - Source: CLAUDE.md

**How to leverage:**
- CodeRabbit auto-applies these learnings in reviews
- Stored in CodeRabbit's knowledge base
- Referenced in path_instructions (.coderabbit.yaml)

---

## 🎯 Issue-Specific Learnings

### Issue #99: Ticket ID vs Number Confusion

**Problem:** Users confused internal database IDs with display numbers
**Impact:** Failed API calls, poor UX

**Solution Implemented:**
1. Show both ID and number in markdown: `Ticket #65003` + `ID: 3`
2. Update tool docstrings with clarification
3. Add helpful error messages when ticket not found

**PR:** #102
**Lessons:**
- UX issues compound over time
- Proactive documentation prevents errors
- Error messages are opportunities to educate

---

### PR #97: MCP Best Practices

**Focus:** Response formats, pagination, agent optimization

**Key Learnings:**
1. Agents need both JSON (programmatic) and markdown (readable) formats
2. Pagination metadata must be accurate for agent decision-making
3. Error messages should guide agents toward correct usage
4. Tool names should reflect agent mental models

**Implemented:**
- `ResponseFormat` enum with JSON/markdown support
- Proper pagination metadata
- Actionable error handling
- Tool annotations for agent hints

---

### PR #101: Pydantic Request Models

**Focus:** Input validation, early error detection

**Breaking Change:** Tools now accept Pydantic models instead of kwargs

**Benefits:**
- Early validation before API calls
- Better error messages
- Enforce constraints (page >= 1, per_page in [1..100])
- Type safety

**Migration Pattern:**
```python
# Before
result = tool("zammad_search_tickets", query="test", page=1)

# After
from mcp_zammad.models import TicketSearchParams
params = TicketSearchParams(query="test", page=1)
result = tool("zammad_search_tickets", params=params)
```

---

## 🔧 Tool-Specific Feedback

### Ruff (Python linter)

**Most Common:**
- `RUF100`: Unused noqa directive
- `BLE001`: Do not catch blind exception
- `PLC0415`: Import should be at top-level (tests)

**Configuration:**
- Line length: 120 characters
- Target: Python 3.10+
- Format + lint in one tool

### GitHub Check: Codacy

**Common Warnings:**
- Cyclomatic complexity > 8
- Function length > 50 lines
- Too many parameters

**Note:** Some warnings are acceptable for MCP tool registration functions.

### LanguageTool (Documentation)

**Common:**
- "GitHub" capitalization (not "github")
- Markdown formatting consistency
- Prose clarity improvements

---

## 📊 Tracking Improvements

### Metrics to Monitor

1. **CodeRabbit comments per PR**
   - Baseline (Q4 2024): ~8-12 comments/PR
   - Target: < 5 comments/PR

2. **Recurring issue rate**
   - Track: Same pattern appears in 2+ PRs
   - Target: 0 recurring issues

3. **Time to first approval**
   - Baseline: ~2-4 hours
   - Target: < 1 hour

4. **Quality score (CodeRabbit)**
   - Track in PR metadata
   - Trend upward over time

---

## 🔄 Update Process

**Monthly Review (30 minutes):**
1. Review last 10 merged PRs
2. Extract new patterns from CodeRabbit comments
3. Update this file with new learnings
4. Update related reference guides if needed
5. Adjust pre-PR checklist

**When to Update:**
- New CodeRabbit pattern appears 2+ times
- Major PR with significant feedback
- New MCP best practice discovered
- Project architecture changes

---

## 📖 Related Documents

- [pagination-patterns.md](./pagination-patterns.md) - Complete pagination guide
- [error-handling-guide.md](./error-handling-guide.md) - Actionable error messages
- [type-annotation-standards.md](./type-annotation-standards.md) - Python 3.10+ typing
- [pre-pr-checklist.md](./pre-pr-checklist.md) - Self-review checklist

---

## 🎓 Learning from CodeRabbit

**Best Practices:**
1. **Don't just fix** - understand the pattern
2. **Document learnings** - update this file
3. **Share knowledge** - update CLAUDE.md and .coderabbit.yaml
4. **Prevent recurrence** - add to checklist
5. **Track metrics** - measure improvement

**When CodeRabbit comments:**
1. Read the full comment + rationale
2. Fix the immediate issue
3. Search codebase for similar patterns
4. Update references/checklist if pattern is common
5. Share learning in team discussions

---

## 🔮 Future Automation

**Planned (Phase 3):**
- Script to extract CodeRabbit comments from PRs
- Auto-generate updates to this file
- Trend analysis of feedback frequency
- Integration with CI/CD for pre-commit validation

**Script stub:** `scripts/extract_feedback.py`
