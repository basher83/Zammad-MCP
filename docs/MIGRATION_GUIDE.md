# Migration Guide: Legacy Wrappers to ZammadMCPServer

## Overview

This guide helps you migrate from deprecated legacy wrapper functions to the recommended `ZammadMCPServer` class-based approach. Legacy wrappers will be removed in v1.0.0.

## Quick Reference

| Legacy Wrapper | New Approach |
|----------------|--------------|
| `from mcp_zammad.server import get_ticket` | `server = ZammadMCPServer(); client = server.get_client()` |
| `await initialize()` | `server = ZammadMCPServer(); await server.initialize()` |
| Module-level functions | Class instance methods |

## Why Migrate?

- **Performance**: New approach includes optimizations like pagination and caching
- **Type Safety**: Better type inference and IDE support
- **Maintainability**: Single source of truth for all operations
- **Future-Proof**: Legacy functions will be removed in v1.0.0

## Migration Patterns

### Pattern 1: Basic Ticket Operations

#### Before (Legacy - Deprecated)

```python
from mcp_zammad.server import initialize, get_ticket, search_tickets

async def my_function():
    await initialize()

    # Search tickets
    tickets = search_tickets(state="open", group="Support")

    # Get specific ticket
    ticket = get_ticket(123, include_articles=True)

    return tickets, ticket
```

#### After (Recommended)

```python
from mcp_zammad.server import ZammadMCPServer
from mcp_zammad.models import Ticket

async def my_function():
    # Create server instance
    server = ZammadMCPServer()
    await server.initialize()

    # Get client
    client = server.get_client()

    # Search tickets
    tickets_data = client.search_tickets(state="open", group="Support")
    tickets = [Ticket(**t) for t in tickets_data]

    # Get specific ticket
    ticket_data = client.get_ticket(123, include_articles=True)
    ticket = Ticket(**ticket_data)

    return tickets, ticket
```

### Pattern 2: Test Migration

#### Before (Legacy - Deprecated)

```python
import pytest
from mcp_zammad.server import initialize, get_user, search_tickets

@pytest.mark.asyncio
async def test_user_tickets(mock_zammad_client):
    mock_instance, _ = mock_zammad_client

    # Mock responses
    mock_instance.get_user.return_value = {"id": 1, "email": "test@example.com"}
    mock_instance.search_tickets.return_value = [{"id": 1, "title": "Test"}]

    # Initialize
    await initialize()
    server.zammad_client = mock_instance

    # Test legacy wrappers
    user = get_user(1)
    tickets = search_tickets(customer="test@example.com")

    assert user.id == 1
    assert len(tickets) == 1
```

#### After (Recommended)

```python
import pytest
from mcp_zammad.server import ZammadMCPServer
from mcp_zammad.models import User, Ticket
from unittest.mock import Mock

def test_user_tickets():
    # Create server with mocked client
    server = ZammadMCPServer()
    server.client = Mock()

    # Mock responses
    server.client.get_user.return_value = {
        "id": 1,
        "email": "test@example.com",
        "firstname": "Test",
        "lastname": "User",
        "login": "test",
        "active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    server.client.search_tickets.return_value = [{
        "id": 1,
        "title": "Test",
        "group_id": 1,
        "state_id": 1,
        "priority_id": 2,
        "customer_id": 1,
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }]

    # Get client
    client = server.get_client()

    # Test methods
    user_data = client.get_user(1)
    user = User(**user_data)

    tickets_data = client.search_tickets(customer="test@example.com")
    tickets = [Ticket(**t) for t in tickets_data]

    assert user.id == 1
    assert len(tickets) == 1
```

### Pattern 3: Ticket Creation

#### Before (Legacy - Deprecated)

```python
from mcp_zammad.server import initialize, create_ticket, add_article

async def create_support_ticket():
    await initialize()

    # Create ticket
    ticket = create_ticket(
        title="Need Help",
        group="Support",
        customer="user@example.com",
        article_body="I need assistance"
    )

    # Add follow-up
    article = add_article(
        ticket_id=ticket.id,
        body="Additional information"
    )

    return ticket
```

#### After (Recommended)

```python
from mcp_zammad.server import ZammadMCPServer
from mcp_zammad.models import Ticket, Article

async def create_support_ticket():
    server = ZammadMCPServer()
    await server.initialize()
    client = server.get_client()

    # Create ticket
    ticket_data = client.create_ticket(
        title="Need Help",
        group="Support",
        customer="user@example.com",
        article_body="I need assistance"
    )
    ticket = Ticket(**ticket_data)

    # Add follow-up
    article_data = client.add_article(
        ticket_id=ticket.id,
        body="Additional information"
    )
    article = Article(**article_data)

    return ticket
```

### Pattern 4: Statistics and Reporting

#### Before (Legacy - Deprecated)

```python
from mcp_zammad.server import initialize, get_ticket_stats, list_groups

async def generate_report():
    await initialize()

    # Get statistics
    stats = get_ticket_stats(group="Support")

    # Get available groups
    groups = list_groups()

    return {"stats": stats, "groups": groups}
```

#### After (Recommended)

```python
from mcp_zammad.server import ZammadMCPServer
from mcp_zammad.models import TicketStats, Group

async def generate_report():
    server = ZammadMCPServer()
    await server.initialize()

    # Access statistics through MCP tool
    # (Note: get_ticket_stats is a tool, accessed differently)
    # For direct client access:
    client = server.get_client()

    # Get groups using caching method
    groups = server._get_cached_groups()

    # For statistics, use the tool directly
    # Or implement client method if needed

    return {"groups": groups}
```

### Pattern 5: User and Organization Management

#### Before (Legacy - Deprecated)

```python
from mcp_zammad.server import (
    initialize,
    search_users,
    get_organization,
    search_organizations
)

async def find_user_org(email: str):
    await initialize()

    # Search for user
    users = search_users(query=email)
    if not users:
        return None

    user = users[0]

    # Get organization
    if user.organization_id:
        org = get_organization(user.organization_id)
        return user, org

    return user, None
```

#### After (Recommended)

```python
from mcp_zammad.server import ZammadMCPServer
from mcp_zammad.models import User, Organization

async def find_user_org(email: str):
    server = ZammadMCPServer()
    await server.initialize()
    client = server.get_client()

    # Search for user
    users_data = client.search_users(query=email)
    if not users_data:
        return None

    user = User(**users_data[0])

    # Get organization
    if user.organization_id:
        org_data = client.get_organization(user.organization_id)
        org = Organization(**org_data)
        return user, org

    return user, None
```

## Function Mapping Reference

### Initialization

- `initialize()` → `server = ZammadMCPServer(); await server.initialize()`
- `zammad_client` → `server.get_client()`

### Ticket Operations

- `search_tickets(...)` → `client.search_tickets(...)`
- `get_ticket(...)` → `client.get_ticket(...)`
- `create_ticket(...)` → `client.create_ticket(...)`
- `update_ticket(...)` → `client.update_ticket(...)`
- `add_article(...)` → `client.add_article(...)`
- `add_ticket_tag(...)` → `client.add_ticket_tag(...)`
- `remove_ticket_tag(...)` → `client.remove_ticket_tag(...)`
- `get_ticket_stats(...)` → Use MCP tool or implement client method

### Attachment Operations

- `get_article_attachments(...)` → `client.get_article_attachments(...)`
- `download_attachment(...)` → `client.download_attachment(...)`

### User Operations

- `get_user(...)` → `client.get_user(...)`
- `search_users(...)` → `client.search_users(...)`
- `get_current_user()` → `client.get_current_user()`

### Organization Operations

- `get_organization(...)` → `client.get_organization(...)`
- `search_organizations(...)` → `client.search_organizations(...)`

### System Operations

- `list_groups()` → `server._get_cached_groups()` or `client.get_groups()`
- `list_ticket_states()` → `server._get_cached_states()` or `client.get_ticket_states()`
- `list_ticket_priorities()` → `server._get_cached_priorities()` or `client.get_ticket_priorities()`

## Common Pitfalls

### ❌ Pitfall 1: Forgetting to Initialize

```python
server = ZammadMCPServer()
client = server.get_client()  # RuntimeError: Zammad client not initialized
```

**✅ Solution:**

```python
server = ZammadMCPServer()
await server.initialize()  # Initialize first!
client = server.get_client()
```

### ❌ Pitfall 2: Not Converting to Pydantic Models

```python
ticket_data = client.get_ticket(123)
print(ticket_data.title)  # AttributeError: 'dict' object has no attribute 'title'
```

**✅ Solution:**

```python
from mcp_zammad.models import Ticket

ticket_data = client.get_ticket(123)
ticket = Ticket(**ticket_data)  # Convert to model
print(ticket.title)  # Works!
```

### ❌ Pitfall 3: Using Module-Level Client in Tests

```python
import server
server.zammad_client = Mock()  # Old pattern
```

**✅ Solution:**

```python
server = ZammadMCPServer()
server.client = Mock()  # New pattern
```

## Testing Migration Checklist

When migrating tests from legacy wrappers to `ZammadMCPServer`:

- [ ] Replace `from mcp_zammad.server import function_name` with `from mcp_zammad.server import ZammadMCPServer`
- [ ] Remove `await initialize()` calls
- [ ] Create `server = ZammadMCPServer()` instance
- [ ] Set `server.client = Mock()` instead of `server.zammad_client = Mock()`
- [ ] Replace function calls with `client.method()` calls
- [ ] Convert dict responses to Pydantic models with `Model(**data)`
- [ ] Update assertions to use model attributes
- [ ] Run tests to verify migration
- [ ] Add `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` if needed temporarily

## Performance Benefits

The new approach includes several performance improvements:

### Intelligent Caching

```python
server = ZammadMCPServer()
await server.initialize()

# First call hits API
groups = server._get_cached_groups()  # API call

# Subsequent calls use cache
groups = server._get_cached_groups()  # Cached!

# Clear cache when needed
server.clear_caches()
```

### Pagination for Large Datasets

```python
# Automatically handles pagination for large datasets
# Old way: loaded all tickets into memory
# New way: processes in batches of 100

# The client methods handle pagination internally
# No code changes needed!
```

### Performance Metrics

```python
# New approach includes automatic logging:
# INFO: Starting ticket statistics calculation
# INFO: Ticket statistics complete: processed 1250 tickets
#       across 13 pages in 2.35s (open=450, closed=600, ...)
```

## Timeline

- **Now - v0.2.0**: Legacy wrappers work but emit `DeprecationWarning`
- **v0.2.0 - v1.0.0**: Migration period (3-6 months)
- **v1.0.0+**: Legacy wrappers removed, must use `ZammadMCPServer`

## Getting Help

If you encounter issues during migration:

1. Review this guide and the examples above
2. Check [`docs/LEGACY_WRAPPER_DEPRECATION.md`](LEGACY_WRAPPER_DEPRECATION.md) for detailed deprecation plan
3. See [`ARCHITECTURE.md`](../ARCHITECTURE.md) for architectural patterns
4. Open a GitHub issue with the `migration` label

## Additional Resources

- **ARCHITECTURE.md**: Detailed architecture documentation
- **CLAUDE.md**: Project-specific development guidance
- **CONTRIBUTING.md**: Development setup and guidelines
- **tests/test_server.py**: Updated test examples

---

**Last Updated**: 2025-10-17
**Applies To**: v0.2.0 and later
