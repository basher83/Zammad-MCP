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

The shipped `zammad_get_ticket` tool (in `ZammadMCPServer._setup_ticket_tools`, `mcp_zammad/server.py`) returns a formatted `str` and delegates not-found detection to `_handle_ticket_not_found_error`. Docstring trimmed:

```python
@self.mcp.tool(annotations=_read_only_annotations("Get Ticket Details"))
@flat_params(GetTicketParams)
def zammad_get_ticket(params: GetTicketParams) -> str:
    """Get detailed information about a specific ticket by ID.

    Parameters:
        ticket_id (int): Internal database ID (NOT display number) (required)
        ...

    Error Handling:
        - Returns TicketIdGuidanceError if ticket not found (suggests using search)
        - Returns "Error: Permission denied" if no access to ticket
        - Returns "Error: Invalid authentication" on 401 status

    Note:
        ticket_id must be the internal database ID, NOT the display number.
        Use the 'id' field from search results, not the 'number' field.
        Example: Ticket #65003 may have id=123. Use id=123 for API calls.
        Large tickets may exceed token limits; use article_limit to control size.
    """
    client = self.get_client()
    try:
        ticket_data = client.get_ticket(
            ticket_id=params.ticket_id,
            include_articles=params.include_articles,
            article_limit=params.article_limit,
            article_offset=params.article_offset,
        )
        ticket = Ticket(**ticket_data)

        # Format response based on preference
        if params.response_format == ResponseFormat.JSON:
            result = json.dumps(ticket.model_dump(), indent=2, default=str)
        else:  # MARKDOWN (default)
            result = _format_ticket_detail_markdown(ticket)

        return truncate_response(result)
    except Exception as e:
        _handle_ticket_not_found_error(params.ticket_id, e)
```

The helper is a module-level function in `mcp_zammad/server.py`. It either raises the guidance error or re-raises the original:

```python
def _handle_ticket_not_found_error(ticket_id: int, error: Exception) -> NoReturn:
    """Check if an exception is a ticket not found error and raise TicketIdGuidanceError.

    Args:
        ticket_id: The ticket ID that was not found
        error: The exception to check

    Raises:
        TicketIdGuidanceError: If the error is a not found error
        Exception: Re-raises the original error if not a not found error
    """
    error_msg = str(error).lower()
    if "not found" in error_msg or "couldn't find" in error_msg:
        raise TicketIdGuidanceError(ticket_id) from error
    raise error
```

`TicketIdGuidanceError` (a `ValueError` subclass in `mcp_zammad/models.py`) carries the message:

```python
self.message = (
    f"Ticket ID {ticket_id} not found. "
    f"Note: Use the internal 'id' field from search results, not the display 'number'. "
    f"Example: For ticket #65003, search first to find its internal ID."
)
```

**Key Elements:**

1. **Docstring guidance**: Prevents mistake before it happens
2. **Error detection**: Catches "not found" pattern
3. **Educational message**: Explains id vs number
4. **Actionable step**: "search first to find internal ID"
5. **Concrete example**: Uses actual ticket from the system

---

### HTTP Status Code Mapping

**Pattern:** Map common HTTP errors to actionable messages.

`_handle_api_error` in `mcp_zammad/server.py` is table-driven. `_resilience_error_message` handles resilience errors (`RetryExhaustedError`, `CircuitOpenError`) first. Then the first matching pattern in `_API_ERROR_GUIDANCE` wins:

```python
_API_ERROR_GUIDANCE: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("not found", "404"),
        "Error: Resource not found during {context}. Please verify the ID is correct and you have access.",
    ),
    (("forbidden", "403"), "Error: Permission denied for {context}. Your credentials lack access to this resource."),
    (("unauthorized", "401"), "Error: Authentication failed for {context}. Check ZAMMAD_HTTP_TOKEN is valid."),
    (("429", "too many requests", "rate limit"), _RATE_LIMIT_GUIDANCE),
    (
        ("timeout",),
        "Error: Request timeout during {context}. The server may be slow - try again or reduce the scope.",
    ),
    (
        ("connection", "network"),
        "Error: Network issue during {context}. Check ZAMMAD_URL is correct and the server is reachable.",
    ),
)


def _resilience_error_message(e: Exception, context: str) -> str | None:
    """Return guidance for retry-exhaustion or open-circuit errors, else None."""
    if isinstance(e, RetryExhaustedError):
        throttled = e.status_code == HTTPStatus.TOO_MANY_REQUESTS
        template = _RATE_LIMIT_GUIDANCE if throttled else _SERVER_ERROR_GUIDANCE
        return template.format(context=context, detail=f" ({e})")
    if isinstance(e, CircuitOpenError):
        return f"Error: Zammad is temporarily unavailable during {context} ({e}). Wait for the recovery timeout."
    return None


def _handle_api_error(e: Exception, context: str = "operation") -> str:
    """Format errors with actionable guidance for LLM agents.

    Args:
        e: The exception that occurred
        context: Description of what was being attempted

    Returns:
        Formatted error message with guidance
    """
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

To add a new HTTP mapping, add a `((patterns...), template)` entry to `_API_ERROR_GUIDANCE`. Do not add an `if`/`elif` branch to `_handle_api_error`.

**Usage in Resources** (`get_ticket_resource` in `_setup_ticket_resource`, trimmed):

```python
@self.mcp.resource("zammad://ticket/{ticket_id}")
def get_ticket_resource(ticket_id: str) -> str:
    """Get a ticket as a resource."""
    client = self.get_client()
    try:
        # Use a reasonable limit for resources to avoid huge responses
        ticket_data = client.get_ticket(int(ticket_id), include_articles=True, article_limit=20)
        ticket = Ticket(**ticket_data)
        ...
        return truncate_response("\n".join(lines))
    except (requests.exceptions.RequestException, ValueError, ValidationError) as e:
        return _handle_api_error(e, context=f"retrieving ticket {ticket_id}")
```

---

### Validation Errors

**Pattern:** Pydantic validation errors should be user-friendly.

Illustrative pattern only. `TicketSearchParams` in `mcp_zammad/models.py` has no `validate_query` validator:

```python
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

```text
ValidationError: Query must be at least 2 characters. Use specific search terms for better results.
```

---

### Configuration Errors

**Pattern:** Missing or invalid configuration.

`ZammadClient.__init__` in `mcp_zammad/client.py` raises `ConfigException` with the corrective action in the message. Trimmed:

```python
class ZammadClient:
    """Wrapper around zammad_py ZammadAPI with additional functionality."""

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        http_token: str | None = None,
        oauth2_token: str | None = None,
        *,
        insecure: bool | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self._audit = audit_logger
        self.url = url or os.getenv("ZAMMAD_URL")
        self.username = username or os.getenv("ZAMMAD_USERNAME")

        # Try to read secrets from files first (Docker secrets pattern)
        self.password = password or self._read_secret_file("ZAMMAD_PASSWORD_FILE") or os.getenv("ZAMMAD_PASSWORD")
        self.http_token = (
            http_token or self._read_secret_file("ZAMMAD_HTTP_TOKEN_FILE") or os.getenv("ZAMMAD_HTTP_TOKEN")
        )
        self.oauth2_token = (
            oauth2_token or self._read_secret_file("ZAMMAD_OAUTH2_TOKEN_FILE") or os.getenv("ZAMMAD_OAUTH2_TOKEN")
        )
        self.insecure = insecure if insecure is not None else ZammadClient._parse_bool_env("ZAMMAD_INSECURE")
        self.resilience = ResilienceConfig.from_env()

        if not self.url:
            raise ConfigException("Zammad URL is required. Set ZAMMAD_URL environment variable.")

        # Validate URL format to prevent SSRF
        self._validate_url(self.url)

        if not any([self.http_token, self.oauth2_token, (self.username and self.password)]):
            # Check if user mistakenly used ZAMMAD_TOKEN
            if os.getenv("ZAMMAD_TOKEN"):
                raise ConfigException(
                    "Found ZAMMAD_TOKEN but this server expects ZAMMAD_HTTP_TOKEN. "
                    "Please rename your environment variable from ZAMMAD_TOKEN to ZAMMAD_HTTP_TOKEN."
                )
            raise ConfigException(
                "Authentication credentials required. Set either ZAMMAD_HTTP_TOKEN, "
                "ZAMMAD_OAUTH2_TOKEN, or both ZAMMAD_USERNAME and ZAMMAD_PASSWORD."
            )
```

URL validation (scheme and further SSRF checks) lives in `ZammadClient._validate_url`.

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
- `mcp_zammad/server.py`: `_handle_ticket_not_found_error`, `_API_ERROR_GUIDANCE`, `_resilience_error_message`, `_handle_api_error`
- `mcp_zammad/models.py`: `TicketIdGuidanceError`
- `mcp_zammad/client.py`: `ZammadClient.__init__`, `ZammadClient._validate_url`
- MCP Best Practices: Error message guidelines
- CodeRabbit PR #97: Error handling feedback
