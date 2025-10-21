# Zammad MCP Server Architecture

This document describes the technical architecture and design decisions of the Zammad MCP Server.

## Overview

The Zammad MCP Server is built on the Model Context Protocol (MCP) to provide AI assistants with structured access to Zammad ticket system functionality. It follows a clean, modular architecture with strong type safety and clear separation of concerns.

## Architecture Diagram

```plaintext
┌─────────────────┐     ┌─────────────────┐
│  Claude/AI      │     │  MCP Client     │
│  Assistant      │────▶│  (Claude App)   │
└─────────────────┘     └────────┬────────┘
                                 │ MCP Protocol
                        ┌────────▼────────┐
                        │   MCP Server    │
                        │  (FastMCP)      │
                        ├─────────────────┤
                        │     Tools       │
                        │   Resources     │
                        │    Prompts      │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │  Zammad Client  │
                        │    Wrapper      │
                        └────────┬────────┘
                                 │ HTTP/REST
                        ┌────────▼────────┐
                        │  Zammad API     │
                        │   Instance      │
                        └─────────────────┘
```

## Core Components

### 1. MCP Server (`server.py`)

The main server implementation using FastMCP framework.

**Responsibilities:**

- MCP protocol implementation
- Tool, resource, and prompt registration
- Request routing and response handling
- Global client lifecycle management

**Key Features:**

- 16 tools for comprehensive Zammad operations
- 3 resources with URI-based access pattern
- 3 pre-configured prompts for common scenarios
- Lifespan management for proper initialization

**Design Patterns:**

- **Singleton Pattern**: Single Zammad client instance
- **Sentinel Pattern**: `_UNINITIALIZED` for type-safe state management
- **Dependency Injection**: Shared client instance across all tools

### 2. Zammad Client (`client.py`)

A wrapper around the `zammad_py` library providing a clean interface.

**Responsibilities:**

- API authentication (token, OAuth2, username/password)
- HTTP request handling
- Response transformation
- Error handling and retries

**Key Methods:**

```python
# Ticket operations
search_tickets(query, state, priority, ...)
get_ticket(ticket_id, include_articles)
create_ticket(title, group, customer, ...)
update_ticket(ticket_id, **kwargs)

# User operations
get_user(user_id)
search_users(query, page, per_page)

# Organization operations
get_organization(org_id)
search_organizations(query, page, per_page)
```

### 3. Data Models (`models.py`)

Comprehensive Pydantic models ensuring type safety and validation.

**Model Hierarchy:**

```plaintext
BaseModel
├── Ticket
│   ├── state: StateBrief | str | None
│   ├── priority: PriorityBrief | str | None
│   ├── group: GroupBrief | str | None
│   ├── owner: UserBrief | str | None
│   └── articles: list[Article] | None
├── User
│   └── organization: Organization | None
├── Organization
├── Group
├── Article
│   ├── type: str
│   ├── sender: str
│   └── internal: bool
└── TicketStats
```

**Validation Features:**

- Automatic type coercion
- Required field validation
- Extra field handling (`extra = "forbid"`)
- Union types for expanded fields (handles both object and string representations)
- Custom validators for complex fields

## Data Flow

### Tool Execution Flow

1. **Request Reception**: MCP client sends tool invocation
1. **Parameter Validation**: FastMCP validates against tool schema
1. **Client Check**: Ensure Zammad client is initialized
1. **API Call**: Execute Zammad API operation
1. **Response Transform**: Convert to Pydantic model
1. **MCP Response**: Return structured data to client

### Resource Access Flow

1. **URI Parsing**: Extract entity type and ID from URI
1. **Direct Fetch**: Retrieve specific entity from Zammad
1. **Model Transform**: Convert to appropriate Pydantic model
1. **Content Generation**: Format for MCP resource response

## Authentication

Supports three authentication methods with precedence:

1. **API Token** (Recommended)

   ```bash
   ZAMMAD_HTTP_TOKEN=your-token
   ```

1. **OAuth2 Token**

   ```bash
   ZAMMAD_OAUTH2_TOKEN=your-oauth-token
   ```

1. **Username/Password**

   ```bash
   ZAMMAD_USERNAME=user
   ZAMMAD_PASSWORD=pass
   ```

## State Management

### Global Client State

```python
_UNINITIALIZED: Final = object()
zammad_client: ZammadClient | object = _UNINITIALIZED

def get_zammad_client() -> ZammadClient:
    """Type-safe client accessor."""
    if zammad_client is _UNINITIALIZED:
        raise RuntimeError("Zammad client not initialized")
    return cast(ZammadClient, zammad_client)
```

### Initialization Lifecycle

```python
@asynccontextmanager
async def lifespan(app: FastMCP):
    """Initialize resources on startup."""
    await initialize()  # Sets up global client
    yield
    # Cleanup if needed

# Note: FastMCP handles its own async event loop
# Do not wrap mcp.run() in asyncio.run()
```

## API Integration Details

### Zammad API Behaviors

1. **Expand Parameter**: When `expand=True` is used:
   - Returns string representations for related objects (e.g., `"group": "Users"`)
   - Does not return full nested objects as might be expected
   - All models use union types to handle both formats:

     ```python
     # Example: Ticket model
     group: GroupBrief | str | None = None
     state: StateBrief | str | None = None
     ```

   - This pattern is applied consistently across all models (Ticket, Article, User, Organization)

1. **Search API**:
   - Uses custom query syntax for filtering
   - Supports field-specific searches (e.g., `state.name:open`)
   - Returns paginated results with metadata

1. **State Handling**: When processing ticket states:
   - Must check if state is a string (expanded) or object (non-expanded)
   - Helper functions may be needed to extract state names consistently

## Error Handling

### Error Hierarchy

1. **Configuration Errors**: Missing credentials, invalid URL
1. **Authentication Errors**: Invalid token, expired credentials
1. **API Errors**: Rate limits, permissions, not found
1. **Validation Errors**: Invalid parameters, type mismatches

### Error Responses

MCP errors include:

- Error code/type
- Human-readable message
- Optional details object

## Performance Considerations

### Current Limitations

1. **Blocking I/O**: Synchronous HTTP calls
1. **No Pooling**: New connections for each request

### Optimizations Implemented

1. **Intelligent Caching**
   - In-memory caching for groups, states, and priorities
   - Reduces repeated API calls for static data
   - Cache invalidation via `clear_caches()` method

1. **Pagination for Statistics**
   - `get_ticket_stats` uses pagination to process tickets in batches
   - Avoids loading entire dataset into memory
   - Configurable safety limit (MAX_PAGES_FOR_TICKET_SCAN)
   - Performance metrics logging (tickets processed, time elapsed, pages fetched)

### Remaining Optimization Opportunities

1. **Enhanced Caching**
   - Redis for distributed cache
   - TTL-based expiration for different data types
   - Cache warming strategies

1. **Connection Pooling**

   ```python
   httpx.Client(
       limits=httpx.Limits(max_keepalive_connections=10)
   )
   ```

1. **Async Implementation**
   - Use `httpx.AsyncClient`
   - Concurrent request handling
   - Better resource utilization

## Security Considerations

### Current Security Measures

- Environment variable configuration
- No credential logging
- HTTPS enforcement for API calls

### Needed Improvements

1. **Input Validation**
   - URL validation to prevent SSRF
   - Input sanitization for user data
   - Parameter bounds checking

1. **Rate Limiting**
   - Client-side rate limiting
   - Exponential backoff
   - Circuit breaker pattern

1. **Audit Logging**
   - Operation logging
   - Security event tracking
   - Compliance support

## Extension Points

### Adding New Tools

1. Define tool function with `@mcp.tool()` decorator
1. Implement using `get_zammad_client()`
1. Return Pydantic model instance
1. Add tests with mocked client

### Adding New Resources

1. Define resource handler with URI pattern
1. Parse entity ID from URI
1. Fetch and transform data
1. Return appropriate content type

### Adding New Prompts

1. Use `@mcp.prompt()` decorator
1. Define parameters and template
1. Include example usage
1. Test with various inputs

## Testing Architecture

### Test Structure

```plaintext
tests/
├── test_server.py      # Main test suite
├── conftest.py         # Shared fixtures
└── test_*.py           # Additional test modules
```

### Mock Strategy

- Mock `ZammadClient` for all tests
- Use factory fixtures for test data
- Parametrize for multiple scenarios
- Cover error paths explicitly

### Coverage Goals

- Target: 80%+ overall coverage (Achieved: 91.7%!)
- 100% for critical paths
- Focus on edge cases and errors

## Future Architecture Considerations

### Microservices Pattern

Consider splitting into:

- Core MCP server
- Zammad client service
- Caching service
- WebSocket service for real-time

### Plugin Architecture

Enable extensions for:

- Custom authentication providers
- Additional ticket sources
- Workflow automation
- Custom prompts/tools

### Scalability

- Horizontal scaling with load balancer
- Distributed caching with Redis
- Message queue for async operations
- Database for audit logs

## Legacy Code Deprecation

### Current State

The codebase contains 19 legacy wrapper functions (`server.py:763-1098`) created during the FastMCP migration to maintain backward compatibility with the test suite. These functions duplicate functionality from the `ZammadMCPServer` class and are slated for removal.

### Deprecation Strategy

**Phase 1 (Completed)**: Fix correctness issues and add performance optimizations
- ✅ Issue #12: Optimized `get_ticket_stats` with pagination
- ✅ Added performance metrics and logging
- ✅ Updated documentation

**Phase 2 (v0.2.0)**: Add deprecation warnings
- Add `DeprecationWarning` to all 19 legacy wrapper functions
- Create comprehensive migration guide
- Update documentation with deprecation notices
- Suppress warnings in existing tests

**Phase 3 (v1.0.0)**: Remove legacy wrappers
- Migrate all tests to `ZammadMCPServer` class
- Remove legacy functions (~335 lines)
- Update documentation
- Major version bump for breaking change

### Benefits of Removal

- **Reduced Code Duplication**: Eliminates ~335 lines of duplicated code
- **Simpler Architecture**: Single, consistent pattern (class-based)
- **Easier Maintenance**: Changes only need to be made once
- **Better Type Safety**: No mixing of module-level and instance patterns

### Detailed Plan

See [`docs/LEGACY_WRAPPER_DEPRECATION.md`](docs/LEGACY_WRAPPER_DEPRECATION.md) for:
- Complete function inventory
- Detailed timeline and milestones
- Migration examples
- Risk assessment
- Action items for each phase
