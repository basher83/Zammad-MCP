# Pre-PR Quality Checklist

## Overview

Use this checklist before creating a PR to catch common issues that Code Rabbit frequently flags. Each item links to detailed guidance in reference docs.

**Estimated time:** 5-10 minutes
**Payoff:** Reduces review iterations by 60-70%

---

## 🎯 Quick Scan (2 minutes)

Run these commands to catch obvious issues:

```bash
# Format code
uv run ruff format mcp_zammad tests

# Check for linting errors
uv run ruff check mcp_zammad tests

# Type check (ignore pre-existing errors)
uv run mypy mcp_zammad 2>&1 | rg "error:" | head -20

# Run tests
uv run pytest
```

---

## ✅ Code Quality Checks

### Type Annotations

→ *See [type-annotation-standards.md](./type-annotation-standards.md)*

- [ ] All functions have return type hints
- [ ] All parameters have type hints
- [ ] Use `list[T]` not `List[T]`
- [ ] Use `dict[K, V]` not `Dict[K, V]`
- [ ] Use `x | None` not `Optional[x]`
- [ ] Use `x | y | z` not `Union[x, y, z]`
- [ ] No parameter shadowing (`type` → `article_type`, `id` → `ticket_id`, `format` → `response_format`)

**Quick check:**

```bash
# Search for legacy typing imports
rg "from typing import (List|Dict|Optional|Union)" mcp_zammad/
```

---

### Pagination (if applicable)

→ *See [pagination-patterns.md](./pagination-patterns.md)*

- [ ] `total` field shows true total (or `None` if unknown), NOT page count
- [ ] `has_more` computed from `total` when available
- [ ] All required fields present: `items`, `total`, `count`, `page`, `per_page`, `offset`, `has_more`, `next_page`, `next_offset`
- [ ] JSON truncation preserves validity (structural, not string truncation)
- [ ] Support both `ResponseFormat.JSON` and `ResponseFormat.MARKDOWN`
- [ ] Documented in docstring that `total` may be `None`

**Quick check:**

```python
# Verify pagination metadata structure
response = {
    "items": [...],
    "total": total_from_api,  # NOT len(items)!
    "count": len(items),
    "has_more": (page * per_page < total) if total is not None else (len(items) == per_page)
}
```

---

### Error Handling

→ *See [error-handling-guide.md](./error-handling-guide.md)*

- [ ] Error messages are actionable (tell user what to do next)
- [ ] Include concrete examples in error messages when helpful
- [ ] Catch specific exceptions, not bare `Exception` (unless re-raised)
- [ ] Use `raise ... from e` for exception chaining
- [ ] Map HTTP errors to user-friendly messages
- [ ] Document common errors in tool docstrings

**Template:**

```python
raise ValueError(
    f"{WHAT_FAILED}. "
    f"Note: {WHY_IT_FAILED}. "
    f"{HOW_TO_FIX}. "
    f"Example: {CONCRETE_EXAMPLE}."
)
```

---

### MCP Tool Implementation

- [ ] Tool uses `@mcp.tool()` decorator
- [ ] Takes Pydantic model as input parameter (post-PR #101)
- [ ] Returns appropriate type (`str`, Pydantic model, etc.)
- [ ] Includes comprehensive docstring with Args/Returns
- [ ] Tool name follows naming convention (`zammad_` prefix)
- [ ] Uses dependency injection (`get_client()`)
- [ ] Handles errors gracefully with actionable messages

**Example:**

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
    }
)
def zammad_search_tickets(params: TicketSearchParams) -> str:
    """Search for tickets with various filters.

    Args:
        params: Search parameters including query, state, priority, pagination

    Returns:
        Formatted response in JSON or Markdown format
    """
    client = self.get_client()
    ...
```

---

### Pydantic Models (if adding/modifying)

- [ ] All fields have type annotations
- [ ] Use `Field()` for validation constraints
- [ ] Use `field_validator` for custom validation
- [ ] HTML sanitization applied where needed
- [ ] Union types handle API response variations (expanded/non-expanded)
- [ ] Docstring explains model purpose

**Example:**

```python
class TicketSearchParams(BaseModel):
    """Parameters for searching tickets."""

    query: str | None = None
    page: int = Field(default=1, ge=1, description="Page number (>= 1)")
    per_page: int = Field(default=25, ge=1, le=100, description="Items per page")
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

---

## 📝 Documentation Checks

- [ ] Docstrings updated for new/modified functions
- [ ] CHANGELOG.md updated (add to Unreleased section)
- [ ] README.md updated if adding public features
- [ ] Tool docstrings clarify ID vs number for ticket operations (if applicable)

---

## 🧪 Testing Checks

- [ ] Tests added for new functionality
- [ ] Tests updated for modified functionality
- [ ] Tests use proper mocking (mock `ZammadClient`)
- [ ] Error cases tested
- [ ] Run full test suite: `uv run pytest`
- [ ] Coverage maintained: `uv run pytest --cov=mcp_zammad`

**Test organization:**

1. Fixtures at top
2. Basic functionality tests
3. Parametrized tests
4. Error/edge case tests

---

## 🔒 Security Checks

- [ ] No secrets or tokens in code
- [ ] User input validated (Pydantic models)
- [ ] HTML sanitization for user-provided text
- [ ] URL validation for SSRF protection (if handling URLs)
- [ ] No SQL injection vectors (we use API, but be aware)

---

## 🎨 Code Style

- [ ] Code formatted with `uv run ruff format`
- [ ] No linting errors: `uv run ruff check`
- [ ] Line length ≤ 120 characters
- [ ] Import statements organized (stdlib, third-party, local)
- [ ] No debug `print()` statements
- [ ] No commented-out code (remove or document why)

---

## 📊 Complexity Checks

- [ ] Functions < 50 lines (except tool registration)
- [ ] Cyclomatic complexity < 10 (use helper functions)
- [ ] No deeply nested logic (> 3-4 levels)
- [ ] Extract complex logic into helper methods

---

## ⚡ Performance Checks (if applicable)

- [ ] Use caching for expensive/repeated operations
- [ ] Pagination used for large result sets
- [ ] Avoid N+1 query patterns
- [ ] Consider memory usage for large datasets

---

## 🔧 Project-Specific Checks

### Zammad MCP Specific

- [ ] Client methods follow existing patterns
- [ ] Resources use URI pattern: `zammad://entity/id`
- [ ] Tool names descriptive and agent-friendly
- [ ] Follow dependency injection pattern
- [ ] Use sentinel pattern for optional initialization

### Issue #99 Context (if touching ticket operations)

- [ ] Markdown shows both ticket number AND internal ID
- [ ] Tool docstrings clarify ID vs number
- [ ] Error messages guide users to use correct ID type

---

## 📋 Pre-Commit Command

Run this before committing:

```bash
# All-in-one quality check
./scripts/quality-check.sh && uv run pytest --cov=mcp_zammad
```

If no quality check script, run:

```bash
uv run ruff format mcp_zammad tests && \
uv run ruff check mcp_zammad tests && \
uv run mypy mcp_zammad && \
uv run pytest --cov=mcp_zammad
```

---

## 🎯 Common CodeRabbit Feedback to Avoid

Based on [coderabbit-learnings.md](./coderabbit-learnings.md):

1. ❌ **Pagination `total` is page count** → Use true total or None
2. ❌ **Using `List[str]` instead of `list[str]`** → Use modern syntax
3. ❌ **Parameter shadowing `type`, `id`, `format`** → Use descriptive names
4. ❌ **Catching bare `Exception`** → Catch specific or re-raise
5. ❌ **JSON truncation breaks validity** → Use structural truncation
6. ❌ **Vague error messages** → Make them actionable
7. ❌ **Missing return type hints** → Add to all functions
8. ❌ **High cyclomatic complexity** → Extract helper functions

---

## ✨ Ready to Submit?

Once all checks pass:

1. ✅ All automated checks passing
2. ✅ Tests passing with good coverage
3. ✅ Checklist items addressed
4. ✅ Documentation updated
5. ✅ Commit message descriptive

**Create PR and watch CodeRabbit** work its magic with fewer comments! 🎉

---

## 📚 Reference Documents

For detailed guidance:

- [pagination-patterns.md](./pagination-patterns.md)
- [error-handling-guide.md](./error-handling-guide.md)
- [type-annotation-standards.md](./type-annotation-standards.md)
- [coderabbit-learnings.md](./coderabbit-learnings.md)

**Questions?** Check CLAUDE.md, .github/copilot-instructions.md, or ask in PR comments.
