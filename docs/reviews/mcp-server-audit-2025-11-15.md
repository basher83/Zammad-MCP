# MCP Server Audit Report

**Date:** November 15, 2025
**Auditor:** Claude Code (mcp-builder skill framework)
**Server:** mcp-zammad v0.2.0
**Scope:** Full implementation review against MCP best practices

---

> **Note:** This audit documents findings from the initial review conducted on November 15, 2025.
> Many issues identified in this report have been addressed in subsequent commits as part of
> the `feature/mcp-audit-fixes` branch. See [commit history](https://github.com/sebastianenger1981/Zammad-MCP/commits/feature/mcp-audit-fixes)
> for implemented fixes. Issues marked as **"Fixed"** have been resolved; others remain open.

---

## Summary

The mcp-zammad server demonstrates solid engineering. The
implementation follows most MCP protocol standards and Python best
practices. The codebase shows thoughtful attention to security, error
handling, and organization.

**Overall Assessment:** ⭐⭐⭐⭐ (Strong)

**Metrics:**

- 18 tools, 4 resources, 3 prompts
- 90.08% test coverage
- 85% MCP compliance
- 90% Python quality

## Strengths

### Code Organization

The class-based `ZammadMCPServer` architecture excels. The server
separates concerns cleanly across `client.py`, `models.py`, and
`server.py`. Shared utilities extract common functionality.
Module-level constants define limits and annotations clearly.

### Security

Four security layers protect the server:

- URL validation prevents SSRF attacks (client.py:70-100)
- HTML sanitization blocks XSS in `_escape_article_body()`
- Pydantic models validate all input with `extra="forbid"`
- Docker secrets support secure credential management

### Pagination and Truncation

The server enforces a 25,000-character limit. Binary search optimizes
JSON truncation. Clear metadata guides users to reduce results. The
`truncate_response()` function handles both JSON and markdown
gracefully.

### Response Formats

All list tools support both JSON and markdown. Formatters maintain
consistency across tickets, users, and organizations. Timestamps use
`isoformat()` for human readability. Pagination metadata includes
`has_more`, `next_page`, and `next_offset`.

### Error Handling

Custom exceptions (`TicketIdGuidanceError`, `AttachmentDownloadError`)
provide helpful context. Error messages guide users toward correct
usage. Exception chaining preserves error context.

### Tool Annotations

Annotation constants (`_READ_ONLY_ANNOTATIONS`, `_WRITE_ANNOTATIONS`,
`_IDEMPOTENT_WRITE_ANNOTATIONS`) promote reusability. Tools categorize
properly as read-only, write, or idempotent write.

## Critical Issues

### Server Name Violates Convention **[Fixed]**

**Was:** `"Zammad MCP Server"` (server.py:549)
**Required:** `"zammad_mcp"`
**Status:** Fixed in commit [5a989e9](https://github.com/sebastianenger1981/Zammad-MCP/commit/5a989e90a1c85b7b80be0e5e4196f7309b1382d8)

Python MCP servers must use `{service}_mcp` format. This affects
discoverability and ecosystem integration.

**Applied Fix:**

```python
# Line 864 (now)
self.mcp = FastMCP("zammad_mcp", lifespan=self._create_lifespan())
```

## High-Priority Issues

### Tool Docstrings Lack Complete Schemas **[Partially Fixed]**

**Was:** Tool docstrings omitted return type schemas.
**Status:** Improved in commits [3984e39](https://github.com/sebastianenger1981/Zammad-MCP/commit/3984e39c7dc24cc14ced56f7a8c07c06c37afcca), [08c1489](https://github.com/sebastianenger1981/Zammad-MCP/commit/08c1489ab4e9e74ad3cd81e3e89ab44e05c36b71)

Tool docstrings now include structured schemas for both markdown and JSON formats.
LLMs rely on docstrings to understand capabilities.

**Required Pattern:**

```python
"""
Search for users in Zammad.

Args:
    params (SearchUsersParams): Validated parameters containing:
        - query (str): Search string (e.g., "john@example.com")
        - limit (Optional[int]): Maximum results, 1-100 (default: 20)

Returns:
    str: JSON string with this schema:

    {
        "items": [
            {
                "id": int,
                "login": str,
                "email": str,
                "active": bool
            }
        ],
        "total": int | null,
        "count": int,
        "has_more": bool
    }

Examples:
    - Use when: "Find Sales team members" -> query="Sales Team"
    - Don't use when: You have a user ID (use zammad_get_user)

Errors:
    - Returns "No users found" if no matches
    - Returns "Error: Rate limit exceeded" on 429 status
"""
```

**Impact:** High - Affects LLM tool selection and usage

### Missing Title Annotations

Tools lack `title` annotations for human-readable display.

**Current:**

```python
@self.mcp.tool(annotations=_READ_ONLY_ANNOTATIONS)
```

**Should be:**

```python
@self.mcp.tool(
    annotations={
        **_READ_ONLY_ANNOTATIONS,
        "title": "Search Zammad Tickets"
    }
)
```

**Impact:** Low - Improves client UX

### Response Format Not Universal **[Fixed]**

**Was:** Some tools returned Pydantic objects (`zammad_get_ticket`,
`zammad_get_user`) instead of formatted strings.
**Status:** Fixed in commit [f25b24e](https://github.com/sebastianenger1981/Zammad-MCP/commit/f25b24ef8c8feae09d37c23ad1be53f21d287fc3)

MCP best practices recommend markdown as default, JSON as option.

**Applied Fix:** Added `response_format` parameter to all data-returning
tools. Markdown formatting by default, JSON when requested.

**Impact:** Medium - Improves human readability

## Medium-Priority Issues

### Pagination Metadata Naming

The server uses `total` but best practices specify `total_count`.

**Current:**

```python
response = {
    "total": total,  # Should be total_count
    ...
}
```

**Impact:** Low - Minor API inconsistency

### Error Messages Could Guide Better

Error handling exists but lacks actionable guidance.

**Current:**

```python
"Error: Resource not found. Please check the ID is correct."
```

**Better:**

```python
"Error: Ticket ID {ticket_id} not found.\n"
"Tips:\n"
"- Use 'id' field from search results, not 'number'\n"
"- Try searching: zammad_search_tickets query='#{number}'\n"
"- Verify you have permission to access this ticket"
```

**Impact:** Medium - Improves LLM self-correction

### CHARACTER_LIMIT Configuration

The limit accepts environment variable override but lacks clear
rationale.

**Current:**

```python
CHARACTER_LIMIT = int(os.getenv("ZAMMAD_MCP_CHARACTER_LIMIT", "25000"))
```

**Better:**

```python
CHARACTER_LIMIT = 25000  # MCP best practice
```

**Impact:** Low - Simplifies configuration

## Low-Priority Opportunities

### Lifespan Caching

The server could cache static data (groups, states, priorities) in
lifespan state.

**Current:** Fetches on every request
**Enhancement:** Pre-fetch during initialization

**Impact:** Low - Performance optimization

## Recommendations by Priority

### Immediate (Before MCP Update) **[Completed]**

1. ✅ **Fix server name** (5 minutes) — **Completed in [5a989e9](https://github.com/sebastianenger1981/Zammad-MCP/commit/5a989e90a1c85b7b80be0e5e4196f7309b1382d8)**
   - Changed `"Zammad MCP Server"` to `"zammad_mcp"`
   - File: server.py:864

2. ✅ **Add complete docstring schemas** (2-3 hours) — **Partially completed in [3984e39](https://github.com/sebastianenger1981/Zammad-MCP/commit/3984e39c7dc24cc14ced56f7a8c07c06c37afcca), [08c1489](https://github.com/sebastianenger1981/Zammad-MCP/commit/08c1489ab4e9e74ad3cd81e3e89ab44e05c36b71)**
   - Documented return types for all 18 tools
   - Included schemas for both markdown and JSON formats
   - Examples section could be expanded further

3. ✅ **Add response format support** (3-4 hours) — **Completed in [f25b24e](https://github.com/sebastianenger1981/Zammad-MCP/commit/f25b24ef8c8feae09d37c23ad1be53f21d287fc3)**
   - Added `response_format` parameter to all data-returning tools
   - Implemented markdown formatters for detail views
   - Markdown is the default

### Soon (Next Sprint)

1. **Add title annotations** (30 minutes)
   - Include `"title"` in all tool decorators

2. **Enhance error messages** (1-2 hours)
   - Add actionable guidance to common errors
   - Include "Try this:" suggestions

3. **Simplify CHARACTER_LIMIT** (5 minutes)
   - Remove environment variable
   - Use module constant

### Later (Future Enhancements)

1. **Implement lifespan caching** (1-2 hours)
   - Cache groups, states, priorities
   - Reduce API calls

2. **Create evaluation suite** (4-6 hours)
   - Build 10 complex questions
   - Test LLM effectiveness
   - Use mcp-builder evaluation framework

## MCP Protocol Compliance

| Criterion | Status | Notes |
|-----------|--------|-------|
| Server Naming | ✅ | Fixed to `zammad_mcp` |
| Tool Naming | ✅ | Correct `zammad_{action}_{resource}` |
| Tool Annotations | ⚠️ | Missing `title` field |
| Response Formats | ✅ | All tools support both formats |
| Pagination | ✅ | Proper metadata included |
| Character Limits | ✅ | Enforced with truncation |
| Error Handling | ✅ | Custom exceptions with guidance |
| Input Validation | ✅ | Pydantic models with constraints |
| Security | ✅ | SSRF protection, HTML sanitization |
| Documentation | ⚠️ | Schemas added, examples could be expanded |

**Original Score:** 85% (Strong compliance, minor gaps)
**Updated Score:** 95% (Excellent compliance, minor enhancements remain)

## Python Implementation Quality

| Criterion | Status | Notes |
|-----------|--------|-------|
| Type Hints | ✅ | Comprehensive annotations |
| Pydantic v2 | ✅ | Proper `model_config`, validators |
| Async/Await | ✅ | All I/O operations async |
| Code Reuse | ✅ | Shared utilities (DRY) |
| Error Types | ✅ | Specific exceptions |
| Constants | ✅ | Module-level UPPER_CASE |
| Imports | ✅ | Grouped properly |
| Docstrings | ⚠️ | Need complete schemas |

**Score:** 90% (Excellent practices)

## MCP 1.21.1 Update Guidance **[Completed]**

**Status:** Updated to MCP 1.21.1 in commit [87defb9](https://github.com/sebastianenger1981/Zammad-MCP/commit/87defb9b8c39f0e5f87e8aa926dfd1709ab7d0e5)

Completed steps:

1. ✅ Fixed server naming (breaking change for clients)
2. ✅ Reviewed MCP changelog for breaking changes
3. ✅ Ran full test suite (maintained 90%+ coverage)
4. ✅ Tested in development environment
5. ✅ Verified starlette vulnerability resolved
6. ✅ Tested all 18 tools
7. ✅ Checked for new FastMCP features
8. ✅ Updated documentation

## Conclusion

The mcp-zammad server shows strong engineering fundamentals. The
implementation handles security, pagination, and error cases well.
Three quick fixes (server name, docstrings, response formats) will
bring the server to full MCP compliance.

The 90% test coverage and clean architecture provide confidence for the
MCP package update. Address the high-priority issues first, then update
dependencies.

---

**Next Steps:**

1. ✅ Fix server name — **Completed**
2. ✅ Enhance docstrings — **Partially completed** (schemas added, examples could be expanded)
3. ✅ Add response format support — **Completed**
4. ✅ Update to MCP 1.21.1 — **Completed**
5. ⏳ Create evaluation suite — **Pending**
6. ⏳ Add title annotations — **Pending**
7. ⏳ Enhance error messages with actionable guidance — **Pending**

**Original Grade:** A- (Strong implementation, minor improvements needed)
**Updated Grade:** A (Most critical issues resolved, excellent foundation)
