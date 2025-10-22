# Pagination Patterns for Zammad MCP

## Overview

Proper pagination implementation is critical for MCP servers to provide reliable data to LLM agents. This guide documents the correct patterns based on CodeRabbit feedback and MCP best practices.

## Core Principle

**Pagination metadata must accurately represent the data state so agents can make informed decisions about fetching more results.**

## Required Pagination Fields

Every paginated JSON response must include:

```python
{
    "items": [...],           # The actual data array
    "total": int | None,      # TRUE total across all pages (None if unknown)
    "count": int,             # Number of items in THIS response
    "page": int,              # Current page number (1-indexed)
    "per_page": int,          # Items per page
    "offset": int,            # Starting position (page - 1) * per_page
    "has_more": bool,         # Whether more pages exist
    "next_page": int | None,  # Next page number if has_more
    "next_offset": int | None # Next offset if has_more
}
```

## Common Mistakes & Fixes

### ❌ WRONG: Using page count as total

```python
# DON'T DO THIS
response = {
    "total": len(tickets),  # This is count, not total!
    "tickets": [ticket.model_dump() for ticket in tickets],
}
```

**Problem:** Agents cannot determine true result set size.

### ✅ CORRECT: True total or None

```python
# DO THIS
def _format_tickets_json(tickets: list[Ticket], total: int | None, page: int, per_page: int) -> str:
    response = {
        "items": [ticket.model_dump() for ticket in tickets],
        "total": total,  # From API if available, None otherwise
        "count": len(tickets),
        ...
    }
```

**When to use None:**

- Zammad API doesn't provide total count
- Expensive to compute total
- Streaming/dynamic results

**When total is None, include metadata:**

```python
"_meta": {
    "total_unknown": True,
    "reason": "Zammad API does not provide total count for searches"
}
```

---

### ❌ WRONG: Inaccurate has_more heuristic

```python
# UNRELIABLE
"has_more": len(tickets) == per_page  # Could be wrong!
```

**Problem:** If last page happens to have exactly per_page items, agents will try to fetch non-existent page.

### ✅ CORRECT: Compute from total when available

```python
# ACCURATE when total is known
"has_more": (page * per_page < total) if total is not None else (len(tickets) == per_page)
```

**For complete lists (groups, states, priorities):**

```python
"has_more": False,  # Always false for cached complete lists
"next_page": None,
"total": len(items)  # Exact count available
```

---

### ❌ WRONG: JSON truncation breaks validity

```python
# DESTROYS JSON
def _truncate_response(content: str, limit: int) -> str:
    if len(content) > limit:
        return content[:limit] + "\n\n⚠️ **Truncated**"  # Invalid JSON!
```

**Problem:** Appending markdown to JSON makes it unparseable.

### ✅ CORRECT: Structural truncation preserves JSON

```python
def _truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    if len(content) <= limit:
        return content

    # Detect and preserve JSON validity
    stripped = content.lstrip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(content)
            original_size = len(content)

            # Binary search to shrink items array
            if "items" in obj and isinstance(obj["items"], list):
                items = obj["items"]
                left, right = 0, len(items)

                while left < right:
                    mid = (left + right + 1) // 2
                    obj["items"] = items[:mid]
                    if len(json.dumps(obj, indent=2, default=str)) <= limit:
                        left = mid
                    else:
                        right = mid - 1

                obj["items"] = items[:left]

            # Add truncation metadata
            meta = obj.setdefault("_meta", {})
            meta.update({
                "truncated": True,
                "original_size": original_size,
                "original_count": len(items),
                "limit": limit,
                "note": "Response truncated; use pagination or filters"
            })

            return json.dumps(obj, indent=2, default=str)
        except Exception:
            pass  # Fall through to markdown truncation

    # Markdown truncation for non-JSON
    truncated = content[:limit]
    truncated += "\n\n⚠️ **Response Truncated**\n"
    truncated += f"Size {len(content)} exceeds limit {limit}.\n"
    truncated += "Use pagination (page/per_page) or filters."
    return truncated
```

## Implementation Checklist

When implementing paginated tools:

- [ ] Accept `page` and `per_page` parameters (validate with Pydantic)
- [ ] Get `total` from API if available, otherwise None
- [ ] Compute `has_more` accurately from total or use heuristic
- [ ] Include all required metadata fields
- [ ] Support both JSON and markdown formats
- [ ] Implement structural JSON truncation
- [ ] Test with: empty results, single page, multiple pages, exact per_page match
- [ ] Document in docstring that total may be None

## Examples from Codebase

### search_tickets (server.py:481-516)

```python
@mcp.tool(...)
def zammad_search_tickets(params: TicketSearchParams) -> str:
    client = self.get_client()

    # Extract params (exclude response_format for API)
    search_params = params.model_dump(exclude={"response_format"}, exclude_none=True)
    tickets_data = client.search_tickets(**search_params)

    tickets = [Ticket(**t) for t in tickets_data]

    # Format response
    if params.response_format == ResponseFormat.JSON:
        # Note: total is None because Zammad doesn't provide it
        result = _format_tickets_json(tickets, None, params.page, params.per_page)
    else:
        result = _format_tickets_markdown(tickets, query_info)

    return _truncate_response(result)
```

### list_groups (server.py:1175-1192)

```python
@mcp.tool(...)
def zammad_list_groups(params: ListParams) -> str:
    groups = self._get_cached_groups()  # Complete list

    if params.response_format == ResponseFormat.JSON:
        # For complete lists, total is known and has_more is always False
        result = _format_list_json(groups)
    else:
        result = _format_list_markdown(groups, "Group")

    return _truncate_response(result)
```

## References

- CodeRabbit PR #97 review: Pagination metadata issues
- MCP Best Practices: Response format guidelines
- server.py: `_format_tickets_json`, `_truncate_response`
