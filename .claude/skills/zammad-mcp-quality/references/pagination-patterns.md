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
    "_meta": {}               # Pre-allocated; truncate_response() writes truncation flags here
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

This is the shipped `_format_tickets_json` in `mcp_zammad/server.py`:

```python
def _format_tickets_json(tickets: list[Ticket], total: int | None, page: int, per_page: int) -> str:
    response: dict[str, Any] = {
        "items": [ticket.model_dump() for ticket in tickets],
        "total": total,  # None when true total is unknown
        "count": len(tickets),
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "has_more": len(tickets) == per_page,  # heuristic when total unknown
        "next_page": page + 1 if len(tickets) == per_page else None,
        "next_offset": page * per_page if len(tickets) == per_page else None,
        "_meta": {},  # Pre-allocated for truncation flags
    }

    return json.dumps(response, indent=2, default=str)
```

**When to use None:**

- Zammad API doesn't provide total count
- Expensive to compute total
- Streaming/dynamic results

**Current state:** The Zammad search endpoint returns no total, so `zammad_search_tickets`, `zammad_search_users` and `zammad_search_organizations` always pass `total=None`. `_format_users_json` and `_format_organizations_json` use the same shape. There is no `_meta.total_unknown` flag. `total: null` is the signal that the total is unknown.

---

### has_more heuristic

The shipped formatters compute `has_more` from the page size only:

```python
"has_more": len(tickets) == per_page,  # heuristic when total unknown
```

**Limitation:** If the last page has exactly `per_page` items, the agent requests one more page and receives an empty result. Zammad does not expose a total, so the project accepts this. An empty page (`count: 0`) is the end signal for the agent.

**If a future endpoint exposes a true total**, compute `has_more` from it and keep the heuristic only as the `None` fallback:

```python
"has_more": (page * per_page < total) if total is not None else (len(tickets) == per_page)
```

Do not document total-aware `has_more` as already implemented. It is not.

**For complete lists (groups, states, priorities, tags)** `_format_list_json` returns everything on page 1:

```python
    # Since these are complete cached lists, pagination shows all items on page 1
    total = len(sorted_items)
    page = 1
    per_page = total
    offset = 0

    response: dict[str, Any] = {
        "items": [item.model_dump() for item in sorted_items],  # type: ignore[attr-defined]
        "total": total,
        "count": total,
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "has_more": False,  # Always false for complete lists
        "next_page": None,
        "next_offset": None,
        "_meta": {},  # Pre-allocated for truncation flags
    }
```

---

### ❌ WRONG: JSON truncation breaks validity

```python
# DESTROYS JSON
def truncate_response(content: str, limit: int) -> str:
    if len(content) > limit:
        return content[:limit] + "\n\n⚠️ **Truncated**"  # Invalid JSON!
```

**Problem:** Appending markdown to JSON makes it unparseable.

### ✅ CORRECT: Structural truncation preserves JSON

The public entry point is `truncate_response` in `mcp_zammad/server.py`. It catches only the exceptions `json.loads` can raise and logs the fallback:

```python
def truncate_response(content: str, limit: int = CHARACTER_LIMIT) -> str:
    """Truncate response with helpful message if over limit.

    For JSON responses, preserves validity by shrinking arrays and adding metadata.
    For markdown/text responses, appends a truncation warning.

    Args:
        content: The content to potentially truncate
        limit: Maximum character limit (default: CHARACTER_LIMIT)

    Returns:
        Original content if under limit, truncated content with warning if over
    """
    if len(content) <= limit:
        return content

    # Try to preserve JSON validity if the content is JSON
    if content.lstrip().startswith(("{", "[")):
        try:
            obj = json.loads(content)
            return _truncate_json_response(content, obj, limit)
        except (json.JSONDecodeError, TypeError) as e:
            # fall back to plaintext truncation if JSON parsing fails
            logger.debug("Failed to parse/truncate JSON response: %s", e, exc_info=True)

    # Plaintext/Markdown truncation
    return _truncate_text_response(content, limit)
```

`_truncate_json_response` shrinks `items` with a binary search (`_find_max_items_for_limit`), switches to compact serialization when the payload is far over the limit, and records what happened in `_meta`:

```python
def _truncate_json_response(content: str, obj: dict[str, Any], limit: int) -> str:
    """Truncate JSON response preserving validity.

    Args:
        content: Original content string
        obj: Parsed JSON object
        limit: Character limit

    Returns:
        Truncated JSON string
    """
    original_size = len(content)
    use_compact = original_size > limit * 1.2

    # Attempt to shrink the "items" array if present
    if "items" in obj and isinstance(obj["items"], list):
        original_items = obj["items"]
        max_items = _find_max_items_for_limit(obj, original_items, limit, use_compact=use_compact)
        obj["items"] = original_items[:max_items]

    # Add metadata about truncation
    meta = obj.setdefault("_meta", {})
    meta.update(
        {
            "truncated": True,
            "original_size": original_size,
            "limit": limit,
            "note": "Response truncated; reduce page/per_page or add filters.",
        }
    )

    # Ensure final JSON (including metadata) fits under limit
    if "items" in obj and isinstance(obj["items"], list):
        json_str = _serialize_json(obj, use_compact=use_compact)
        while obj["items"] and len(json_str) > limit:
            obj["items"].pop()
            json_str = _serialize_json(obj, use_compact=use_compact)

    return _serialize_json(obj, use_compact=use_compact)
```

`CHARACTER_LIMIT` is a module constant (`CHARACTER_LIMIT = 25000`). No code reads it from the environment.

## Implementation Checklist

When implementing paginated tools:

- [ ] Accept `page` and `per_page` parameters (validate with Pydantic)
- [ ] Take `total` from the API if available, otherwise None
- [ ] Compute `has_more` from `total` when known. Otherwise use the `len(items) == per_page` heuristic
- [ ] Include all required metadata fields
- [ ] Support both JSON and markdown formats
- [ ] Return through `truncate_response()` so JSON stays valid
- [ ] Test with: empty results, single page, multiple pages, exact per_page match
- [ ] Document in docstring that total may be None

## Examples from Codebase

The `ZammadMCPServer._setup_*` methods register the tools. The `@self.mcp.tool(...)` decorator wraps `@flat_params(Model)`. Without `flat_params` the tool advertises one nested `params` object that MCP clients cannot send (see `mcp_zammad/tool_params.py`).

### `zammad_search_tickets` (in `_setup_ticket_tools`)

```python
@self.mcp.tool(annotations=_read_only_annotations("Search Tickets"))
@flat_params(TicketSearchParams)
def zammad_search_tickets(params: TicketSearchParams) -> str:
    """Search for tickets with filters and pagination. ..."""
    client = self.get_client()

    # Extract search parameters (exclude response_format for API call)
    search_params = params.model_dump(exclude={"response_format"}, exclude_none=True)
    tickets_data = client.search_tickets(**search_params)

    tickets = [Ticket(**ticket) for ticket in tickets_data]
    ...
    # Format response
    if params.response_format == ResponseFormat.JSON:
        result = _format_tickets_json(tickets, None, params.page, params.per_page)
    else:
        result = _format_tickets_markdown(tickets, query_info)

    return truncate_response(result)
```

### `zammad_list_groups` (in `_setup_system_tools`)

```python
@self.mcp.tool(annotations=_read_only_annotations("List Groups"))
@flat_params(ListParams)
def zammad_list_groups(params: ListParams) -> str:
    """Get complete list of all available groups (cached). ..."""
    groups = self._get_cached_groups()

    # Format response
    if params.response_format == ResponseFormat.JSON:
        result = _format_list_json(groups)
    else:
        result = _format_list_markdown(groups, "Group")

    return truncate_response(result)
```

## References

- CodeRabbit PR #97 review: Pagination metadata issues
- MCP Best Practices: Response format guidelines
- `mcp_zammad/server.py`: `_format_tickets_json`, `_format_list_json`, `truncate_response`, `_truncate_json_response`, `_find_max_items_for_limit`
- `mcp_zammad/tool_params.py`: `flat_params`
