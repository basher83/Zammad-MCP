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

**Current state:** Not implemented. `mcp_zammad/server.py` still defines the module constant:

```python
CHARACTER_LIMIT = 25000  # Maximum response size per MCP best practices
```

There is no `ZAMMAD_MCP_CHARACTER_LIMIT` environment variable. `truncate_response(content, limit=CHARACTER_LIMIT)` accepts a `limit` argument, so a caller can override it per call. Treat an environment override as an open suggestion, not a shipped feature.

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
Large, deeply nested functions are hard to maintain and test. The project limits are in AGENTS.md section 8: nesting depth ≤ 3, every construct ≤ 30 lines, every file ≤ 200 lines.

**CodeRabbit Warnings (historical):**

- `_handle_api_error`: complexity 10
- `_setup_ticket_tools`: complexity 24

**Solution:**

- Extract error-specific handlers into separate functions
- Break large setup methods into smaller helpers
- Use dictionaries/mappings instead of long if/elif chains

**Shipped Refactor:** `_handle_api_error` is now table-driven. The `(patterns, template)` tuples live in `_API_ERROR_GUIDANCE`, resilience errors go through `_resilience_error_message`, and the function body is one loop:

```python
def _handle_api_error(e: Exception, context: str = "operation") -> str:
    resilience_message = _resilience_error_message(e, context)
    if resilience_message is not None:
        return resilience_message

    error_msg = str(e).lower()

    # First matching pattern wins; order mirrors the original precedence.
    for patterns, template in _API_ERROR_GUIDANCE:
        if any(pattern in error_msg for pattern in patterns):
            return template.format(context=context, detail="")

    # Generic error with type information
    return f"Error during {context}: {type(e).__name__} - {e}"
```

See [error-handling-guide.md](./error-handling-guide.md) for the full table.

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

CodeRabbit has a "Learnings" feature that tracks project-specific patterns.

**Where learnings live:** In CodeRabbit's hosted knowledge base, not in this repository. `.coderabbit.yaml` only enables the feature (`knowledge_base.learnings.scope: auto`). It holds no learning text. Read them in the CodeRabbit dashboard or in review comments.

**What `.coderabbit.yaml` does hold:** `reviews.path_instructions` (per-path review guidance for `server.py`, `client.py`, `models.py`, `tests/`, shell scripts, workflows and the Dockerfile) and `path_filters`. Note that `path_filters` excludes `!**/.claude/**`, so CodeRabbit never reviews this skill.

**Learnings recorded from past reviews** (dates from the CodeRabbit UI):

1. **2025-07-24:** "Use FastMCP framework for MCP server implementation" (applies to `mcp_zammad/**/*.py`)
2. **2025-10-21:** "Define MCP prompts in server.py using the mcp.prompt() decorator" (applies to `mcp_zammad/server.py`)

**How to leverage:**

- CodeRabbit auto-applies its stored learnings in reviews
- To make a rule visible in the repo, add it to `reviews.path_instructions` in `.coderabbit.yaml` or to AGENTS.md

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

### Codacy

PR #369 removed the no-op Codacy SARIF workflow, so there is no Codacy code-quality check on PRs. What remains is a conditional coverage upload in `.github/workflows/tests.yml` (only on Python 3.13 and only when the `CODACY_PROJECT_TOKEN` secret exists). The structural limits that apply are the AGENTS.md section 8 limits above, enforced in review.

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
3. **Share knowledge** - update AGENTS.md and .coderabbit.yaml
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

**Script stub:** `scripts/extract_feedback.py` (prints `[TODO]` placeholders, not functional)
