# Type Annotation Standards for Zammad MCP

## Overview

The Zammad MCP project uses **Python 3.10+** type syntax with strict MyPy checking. Modern type annotations improve code quality, IDE support, and catch errors before runtime.

## Core Rules

1. **Use Python 3.10+ syntax** (not typing module legacy syntax)
2. **Type hint all functions and methods**
3. **Use union syntax with `|`** not `Optional` or `Union`
4. **Avoid parameter shadowing** (use `article_type` not `type`)
5. **Narrow `T | None` with a guard clause. Use `typing.cast` only as a last resort**

## Modern Syntax Reference

### ✅ DO: Python 3.10+ Syntax

```python
# Collection types
items: list[str]                  # NOT List[str]
mapping: dict[str, int]           # NOT Dict[str, int]
values: tuple[int, ...]           # NOT Tuple[int, ...]
unique: set[str]                  # NOT Set[str]

# Union types
def process(value: str | None):   # NOT Optional[str]
def handle(x: int | str | None):  # NOT Union[int, str, None]

# Type aliases
UserId: TypeAlias = int | str     # Modern syntax

# Function signatures
def search_tickets(
    query: str | None = None,
    page: int = 1,
    per_page: int = 25
) -> list[Ticket]:                # Return type always specified
    ...
```

### ❌ DON'T: Legacy typing Module Syntax

```python
from typing import List, Dict, Optional, Union  # Deprecated for builtins

# OLD (pre-3.10)
items: List[str]                  # Use list[str]
mapping: Dict[str, int]           # Use dict[str, int]
value: Optional[str]              # Use str | None
result: Union[int, str]           # Use int | str
```

---

## Parameter Shadowing

### ❌ DON'T: Shadow built-in names or type names

```python
# BAD - shadows built-in
def create_article(type: str, body: str):  # 'type' is a built-in!
    ...

# BAD - shadows the Ticket model name with a plain dict
def process_ticket(ticket: dict):  # readers expect a Ticket model here
    ...
```

Note: `def f(ticket: Ticket, ticket: dict)` is a `SyntaxError` (duplicate argument), not shadowing. Python rejects it before any linter runs.

### ✅ DO: Use descriptive parameter names

```python
# GOOD
def create_article(article_type: str, body: str):
    ...

# GOOD
def process_ticket(ticket: Ticket, ticket_data: dict):
    ...
```

**Common shadowing fixes:**

- `type` → `article_type`, `resource_type`, `entity_type`
- `id` → `ticket_id`, `user_id`, `org_id`
- `format` → `response_format`, `output_format`
- `filter` → `filters`, `filter_expr`

---

## Pydantic Models

### Type annotations in models

```python
from pydantic import BaseModel, Field

class TicketSearchParams(BaseModel):
    """Parameters for searching tickets."""

    # Required field
    query: str

    # Optional with default
    page: int = 1

    # Optional without default (can be None)
    state: str | None = None

    # With Field for validation
    per_page: int = Field(default=25, ge=1, le=100)

    # Union of types
    priority: int | str | None = None

    # Complex types
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Union types for API flexibility

```python
class Ticket(BaseModel):
    """Ticket model handling both expanded and non-expanded API responses."""

    id: int
    number: str
    title: str

    # Can be ID (int) or expanded object (StateBrief) or name (str)
    state: int | StateBrief | str | None = None
    priority: int | PriorityBrief | str | None = None

    # Always a specific type
    created_at: datetime
    updated_at: datetime

    # Optional fields
    customer_id: int | None = None
    owner_id: int | None = None
```

---

## Type Narrowing: `ZammadClient | None` and lazy initialization

The server does not use a sentinel class or `typing.cast` for the client. `ZammadMCPServer` (in `mcp_zammad/server.py`) declares the attribute as `ZammadClient | None` and narrows it with a guard in `get_client`, which lazily creates the client when it is missing:

```python
class ZammadMCPServer:
    def __init__(self, ...) -> None:
        ...
        self.client: ZammadClient | None = None
        ...

    def get_client(self) -> ZammadClient:
        """Get the Zammad client, ensuring it's initialized."""
        if not self.client:
            logger.debug("Zammad client not initialized, performing lazy initialization")
            self.client = self._create_client(verify_connection=False)
        return self.client
```

MyPy narrows `self.client` to `ZammadClient` after the assignment inside the guard, so the code needs no `cast()`. Tools call `self.get_client()` instead of reading `self.client` directly.

### When `cast()` is still appropriate

Use `typing.cast` only when the checker cannot follow a narrowing you have already proven at runtime (for example, a `dict[str, Any]` value you checked with `isinstance`). Prefer a guard clause or a Pydantic model over `cast` where either works.

---

## Function Signatures

### Complete type hints

```python
# GOOD: Full type annotations
def format_tickets_json(
    tickets: list[Ticket],
    total: int | None,
    page: int,
    per_page: int
) -> str:
    """Format tickets as JSON.

    Args:
        tickets: List of ticket objects
        total: Total count (None if unknown)
        page: Current page number
        per_page: Items per page

    Returns:
        JSON-formatted string
    """
    response: dict[str, Any] = {
        "items": [t.model_dump() for t in tickets],
        "total": total,
        ...
    }
    return json.dumps(response, indent=2, default=str)
```

### Avoid `Any` when possible

```python
# Less type-safe
def process_data(data: Any) -> Any:
    ...

# Better - be specific
def process_data(data: dict[str, str | int]) -> list[str]:
    ...

# When Any is necessary, document why
def serialize(obj: Any) -> str:  # Any needed for json.dumps compatibility
    """Serialize any JSON-compatible object."""
    return json.dumps(obj, default=str)
```

---

## Async Function Types

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Async function
async def initialize() -> None:
    client = ZammadClient()
    ...

# Async generator
async def stream_tickets() -> AsyncIterator[Ticket]:
    async for ticket in api.stream():
        yield ticket

# Async context manager
@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    await initialize()
    try:
        yield
    finally:
        await cleanup()
```

---

## Common Patterns in Zammad MCP

### Tool function signatures

```python
@self.mcp.tool(annotations=_read_only_annotations("Search Tickets"))
@flat_params(TicketSearchParams)
def zammad_search_tickets(params: TicketSearchParams) -> str:
    """Search for tickets.

    Args:
        params: Pydantic model with search parameters

    Returns:
        Formatted response (JSON or markdown)
    """
    ...
```

### Resource handler signatures

```python
@self.mcp.resource("zammad://ticket/{ticket_id}")
def get_ticket_resource(ticket_id: str) -> str:
    """Get ticket resource.

    Args:
        ticket_id: Ticket ID as string from URI

    Returns:
        Formatted ticket data
    """
    ...
```

### Client method signatures

```python
class ZammadClient:
    def search_tickets(
        self,
        query: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        page: int = 1,
        per_page: int = 25
    ) -> list[dict[str, Any]]:
        """Search for tickets.

        Args:
            query: Search query string
            state: Filter by state name
            priority: Filter by priority
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            List of ticket dictionaries from API
        """
        ...
```

---

## MyPy Configuration

MyPy is a hard gate in `scripts/validate.sh` (`mise run validate`). The configuration in `pyproject.toml` is:

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = true
```

`strict = true` is not set. Per-module overrides follow in `[[tool.mypy.overrides]]`.

**Common MyPy errors and fixes:**

### Error: Function is missing a return type annotation

```python
# BAD
def process():
    return "result"

# GOOD
def process() -> str:
    return "result"
```

### Error: Need type annotation for variable

```python
# BAD
response = {}

# GOOD
response: dict[str, Any] = {}
```

---

## Type Annotation Checklist

When writing or reviewing code:

- [ ] All functions have return type hints
- [ ] All function parameters have type hints
- [ ] Use `list[T]` not `List[T]`
- [ ] Use `dict[K, V]` not `Dict[K, V]`
- [ ] Use `x | None` not `Optional[x]`
- [ ] Use `x | y` not `Union[x, y]`
- [ ] No parameter shadowing (`type`, `id`, `format`, etc.)
- [ ] Complex types documented in docstrings
- [ ] Pydantic models use Field() for validation
- [ ] Optional attributes typed `T | None` and narrowed with a guard clause. Use `cast()` only as a last resort
- [ ] MyPy runs without errors (`mise run validate`)

## References

- Python 3.10+ typing documentation
- AGENTS.md: Python conventions and code structure constraints
- `mcp_zammad/server.py`: `ZammadMCPServer.get_client`
- CodeRabbit PR #97: Type annotation feedback
- PEP 604: Union type syntax
- PEP 585: Type hinting generics in standard collections
