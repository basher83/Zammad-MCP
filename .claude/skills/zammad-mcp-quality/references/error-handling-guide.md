# Error Handling Guide for Zammad MCP

## Overview

Error messages in MCP servers must be **actionable and educational** for LLM agents. Good error messages guide agents toward correct usage patterns, not just report failures.

## Core Principles

1. **Actionable**: Tell the agent what to do next
2. **Educational**: Explain the correct pattern
3. **Specific**: Include concrete examples
4. **Context-aware**: Tailor to the likely mistake

## Error Message Template

```python
f"{WHAT_FAILED}. "
f"Note: {WHY_IT_FAILED}. "
f"{HOW_TO_FIX}. "
f"Example: {CONCRETE_EXAMPLE}."
```

## Pattern Catalog

### ID vs Number Confusion (Issue #99)

**Problem:** Users confuse internal database IDs with display numbers.

**Example:** Ticket #65003 has internal ID=3, but users try `get_ticket(65003)`

#### ✅ CORRECT Implementation

```python
def zammad_get_ticket(params: GetTicketParams) -> Ticket:
    """Get detailed information about a specific ticket.

    Args:
        params: Get ticket parameters including ticket_id.
               ticket_id must be the internal database ID (NOT the display number).
               Use the 'id' field from search results, not the 'number' field.
               Example: For "Ticket #65003", use the 'id' value from search results.

    Returns:
        Ticket details including articles if requested
    """
    client = self.get_client()
    try:
        ticket_data = client.get_ticket(
            ticket_id=params.ticket_id,
            include_articles=params.include_articles,
            article_limit=params.article_limit,
            article_offset=params.article_offset,
        )
        return Ticket(**ticket_data)
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg or "couldn't find" in error_msg:
            raise ValueError(
                f"Ticket ID {params.ticket_id} not found. "
                f"Note: Use the internal 'id' field from search results, not the display 'number'. "
                f"Example: For ticket #65003, search first to find its internal ID."
            ) from e
        raise
```

**Key Elements:**
1. **Docstring guidance**: Prevents mistake before it happens
2. **Error detection**: Catches "not found" pattern
3. **Educational message**: Explains id vs number
4. **Actionable step**: "search first to find internal ID"
5. **Concrete example**: Uses actual ticket from the system

---

### HTTP Status Code Mapping

**Pattern:** Map common HTTP errors to actionable messages

```python
def _handle_api_error(e: Exception, context: str = "operation") -> str:
    """Format errors with actionable guidance for LLM agents.

    Args:
        e: The exception that occurred
        context: Description of what was being attempted

    Returns:
        Formatted error message with guidance
    """
    error_msg = str(e).lower()

    # 404: Not Found
    if "not found" in error_msg or "404" in error_msg:
        return (
            f"Error: Resource not found during {context}. "
            f"Please verify the ID is correct and you have access."
        )

    # 403: Forbidden
    if "forbidden" in error_msg or "403" in error_msg:
        return (
            f"Error: Permission denied for {context}. "
            f"Your credentials lack access to this resource."
        )

    # 401: Unauthorized
    if "unauthorized" in error_msg or "401" in error_msg:
        return (
            f"Error: Authentication failed for {context}. "
            f"Check ZAMMAD_HTTP_TOKEN is valid."
        )

    # Timeout
    if "timeout" in error_msg:
        return (
            f"Error: Request timeout during {context}. "
            f"The server may be slow - try again or reduce the scope."
        )

    # Connection
    if "connection" in error_msg or "network" in error_msg:
        return (
            f"Error: Network issue during {context}. "
            f"Check ZAMMAD_URL is correct and the server is reachable."
        )

    # Generic fallback
    return f"Error during {context}: {type(e).__name__} - {e}"
```

**Usage in Resources:**

```python
@self.mcp.resource("zammad://ticket/{ticket_id}")
def get_ticket_resource(ticket_id: str) -> str:
    client = self.get_client()
    try:
        ticket = client.get_ticket(int(ticket_id), include_articles=True, article_limit=20)
        # ... format response ...
        return _truncate_response("\n".join(lines))
    except (requests.exceptions.RequestException, ValueError) as e:
        return _handle_api_error(e, context=f"retrieving ticket {ticket_id}")
```

---

### Validation Errors

**Pattern:** Pydantic validation errors should be user-friendly

```python
# In models.py
class TicketSearchParams(BaseModel):
    """Parameters for searching tickets."""

    query: str | None = None
    page: int = Field(default=1, ge=1, description="Page number (must be >= 1)")
    per_page: int = Field(default=25, ge=1, le=100, description="Items per page (1-100)")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 2:
            raise ValueError(
                "Query must be at least 2 characters. "
                "Use specific search terms for better results."
            )
        return v
```

**Error raised:**
```
ValidationError: Query must be at least 2 characters. Use specific search terms for better results.
```

---

### Configuration Errors

**Pattern:** Missing or invalid configuration

```python
# In client.py
class ZammadClient:
    def __init__(self):
        self.url = os.getenv("ZAMMAD_URL")
        if not self.url:
            raise ConfigException(
                "ZAMMAD_URL environment variable is required. "
                "Set it to your Zammad instance API endpoint (e.g., https://instance.zammad.com/api/v1). "
                "Check .env.example for configuration template."
            )

        # Validate URL format
        if not self.url.startswith(("http://", "https://")):
            raise ConfigException(
                f"ZAMMAD_URL must start with http:// or https://. "
                f"Got: {self.url}. "
                f"Example: https://your-instance.zammad.com/api/v1"
            )
```

---

## Error Handling Checklist

When implementing error handling:

- [ ] Catch specific exceptions, not bare `Exception` (unless re-raised)
- [ ] Provide actionable next steps in error message
- [ ] Include concrete examples when helpful
- [ ] Map generic errors to specific contexts
- [ ] Document common errors in tool docstrings
- [ ] Test error paths in unit tests
- [ ] Consider what the agent needs to know to proceed
- [ ] Use proper exception chaining (`raise ... from e`)

## Anti-Patterns

### ❌ DON'T: Vague error messages

```python
# BAD
raise ValueError("Invalid input")

# BAD
return "Error: Something went wrong"
```

### ❌ DON'T: Technical jargon without context

```python
# BAD
raise ValueError("HTTP 422: Unprocessable Entity")

# BETTER
raise ValueError(
    "Server rejected the request due to invalid data. "
    "Check that all required fields are provided and properly formatted."
)
```

### ❌ DON'T: Catch and ignore errors silently

```python
# DANGEROUS
try:
    result = client.get_ticket(ticket_id)
except Exception:
    pass  # Silent failure!
```

### ❌ DON'T: Expose internal implementation details

```python
# BAD
raise ValueError(f"ZammadAPI._make_request failed: {traceback.format_exc()}")

# BETTER
raise ValueError(
    f"Failed to fetch ticket {ticket_id}. "
    f"Verify the ticket exists and you have permission to access it."
)
```

## References

- Issue #99: Ticket ID vs Number confusion
- server.py:279-308: `_handle_api_error` implementation
- MCP Best Practices: Error message guidelines
- CodeRabbit PR #97: Error handling feedback
