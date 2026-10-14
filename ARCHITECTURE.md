# Zammad MCP Server Architecture

This document describes the technical architecture and design decisions of the Zammad MCP Server.

## Overview

The Zammad MCP Server is built on the Model Context Protocol (MCP) to provide AI assistants with structured access to Zammad ticket system functionality. It follows a clean, modular architecture with strong type safety and clear separation of concerns.

## Architecture Diagram

```text
┌─────────────────┐     ┌─────────────────┐
│  Claude/AI      │     │  MCP Client     │
│  Assistant      │────▶│  (Claude App)   │
└─────────────────┘     └────────┬────────┘
                                 │ MCP Protocol
                        ┌────────▼────────┐
                        │  OAuth Proxy    │ (optional: Zammad Doorkeeper)
                        │  (FastMCP)      │
                        ├─────────────────┤
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
                                 │ HTTP/REST (user's token forwarded)
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
- Per-server client lifecycle management

**Key Features:**

- 31 tools for comprehensive Zammad operations
- 7 resources with URI-based access pattern
- 3 pre-configured prompts for common scenarios
- Lifespan management for proper initialization

**Design Patterns:**

- **Instance-local state**: Each `ZammadMCPServer` owns its client
- **Lifespan management**: Startup initializes the client and shutdown clears it
- **Per-request client**: When OAuth is enabled, a new `ZammadClient` is created per request using the authenticated user's Zammad bearer token

### 2. Zammad Client (`client.py`)

A wrapper around the `zammad_py` library providing a clean interface.

**Responsibilities:**

- API authentication (token, OAuth2, username/password)
- HTTP request handling
- Response transformation
- Error handling

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

```text
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

### Module Map

One row per module in `mcp_zammad/`. Each responsibility is the first line of the module docstring.

| Module | Responsibility |
|--------|----------------|
| `__init__.py` | Zammad MCP Server - Model Context Protocol server for Zammad ticket system |
| `__main__.py` | Entry point for the Zammad MCP server |
| `audit.py` | Opt-in JSON Lines audit logging for security-relevant MCP operations |
| `audit_middleware.py` | FastMCP middleware that audits every tool invocation |
| `client.py` | Zammad API client wrapper for the MCP server |
| `config.py` | Configuration for MCP server transport |
| `docstring_templates.py` | Helper functions for generating MCP tool docstrings per best practices |
| `events.py` | Bounded in-memory retention of normalized Zammad webhook events |
| `logging_config.py` | Logging configuration helpers for Zammad MCP |
| `models.py` | Pydantic models for Zammad entities |
| `resilience.py` | Resilient transport wrapper around the `requests.Session` that zammad-py uses for every call |
| `resilience_config.py` | Environment-backed configuration for client-side rate limiting, retries, and circuit breaking |
| `resilience_retry.py` | Retry policy for safe HTTP methods: which outcomes retry, how long to wait, and the attempt loop |
| `resilience_state.py` | Process-local rate limiter and circuit breaker state driven by an injected monotonic clock |
| `server.py` | Zammad MCP Server implementation |
| `tool_params.py` | Expose Pydantic parameter models as flat MCP tool arguments |
| `webhooks.py` | Zammad webhook delivery boundary: signature validation and payload normalization |

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

## Upstream Zammad Authentication

These credentials authenticate the server to Zammad. Unless OAuth mode (below) is enabled, HTTP transport provides no
inbound MCP client authentication; remote deployments then need an authenticated proxy or another trusted-network control.

The server supports two authentication modes:

### Mode 1: OAuth via Zammad Doorkeeper (multi-user)

When `MCP_AUTH_*` env vars are configured, the server uses FastMCP's `OAuthProxy`
to proxy the OAuth flow to Zammad's built-in Doorkeeper authorization server.
Users authenticate through Zammad's login page (which may offer Google, GitHub,
etc. depending on the instance's config). The resulting Zammad bearer token is
forwarded to the API — each user acts under their own identity.

```bash
MCP_AUTH_CLIENT_ID=...                          # Zammad OAuth app client ID
MCP_AUTH_CLIENT_SECRET=...                      # Zammad OAuth app client secret
MCP_AUTH_BASE_URL=https://localhost:8000        # This MCP server's URL
# OAuth endpoints (/oauth/authorize, /oauth/token) derived from ZAMMAD_URL
```

Configuration is handled by `AuthConfig` in `config.py`, which creates an
`OAuthProxy` pointing at Zammad's endpoints and passes it to `FastMCP(auth=...)`.

### Mode 2: Static Credentials (single-user / service account)

When no OAuth env vars are configured, the server uses static credentials with
the following precedence:

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

### Server Client State

Each `ZammadMCPServer` stores its client on `self.client`. Tool handlers obtain the initialized instance through
`self.get_client()`. If startup has not created the client yet, `get_client()` creates it on first use, without the
startup connection check.

In OAuth mode, `get_client()` instead retrieves the authenticated user's Zammad bearer token via FastMCP's
`get_access_token()` and creates a per-request `ZammadClient` with that token; no client is created at startup.

### Initialization Lifecycle

```python
@asynccontextmanager
async def lifespan(_app: FastMCP):
    await self.initialize()
    try:
        yield
    finally:
        self.client = None

# Note: FastMCP handles its own async event loop
# Do not wrap mcp.run() in asyncio.run()
```

## API Integration Details

### Zammad API Behaviors

1. **Expand Parameter**: The client sends `expand="true"` as a lowercase string:
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

1. **Blocking I/O**: Synchronous HTTP calls. Each `ZammadClient` sends every request through one `requests.Session`
   (wrapped by `ResilientSession`), so connections are reused, but one call blocks until it finishes.

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

1. **Async Implementation**
   - Replace the synchronous zammad-py client with an async HTTP client such as `httpx.AsyncClient`
   - Concurrent request handling
   - Better resource utilization

## Security Considerations

### Current Security Measures

- Environment variable configuration
- No credential logging
- TLS certificate verification on by default. The client accepts `http://` and `https://` URLs and
  disables verification only when you set `ZAMMAD_INSECURE` to `1`, `true`, `yes`, or `on` (for trusted
  self-signed or internal certificate chains). The client logs a warning when verification is off.
- URL scheme and hostname validation for `ZAMMAD_URL` (`ZammadClient._validate_url`). The client warns
  and audits when the host is `localhost` or a private or loopback IP literal, but does not block it.
- Opt-in audit logging (`mcp_zammad/audit.py`, `mcp_zammad/audit_middleware.py`): JSON Lines events for
  every tool invocation, Zammad connection attempts, and URL security checks.
- Resilience layer (`mcp_zammad/resilience*.py`): `ZammadClient` replaces the `zammad_py`
  `requests.Session` with a `ResilientSession`, so every API call passes through one boundary that
  applies an opt-in fixed-window rate limiter, exponential backoff with `Retry-After` support for
  safe methods only, and a closed/open/half-open circuit breaker. State is process-local; the clock
  and sleeper are injected so behavior is deterministic under test.

### Needed Improvements

1. **Input Validation**
   - SSRF hardening for `ZAMMAD_URL` (current validation checks scheme and hostname only and does not
     block local or private targets)
   - Input sanitization for user data
   - Parameter bounds checking

## Extension Points

### Adding New Tools

1. Define a parameters model in `models.py` that extends `StrictBaseModel`
1. Register the tool inside a `ZammadMCPServer._setup_*` method with
   `@self.mcp.tool(annotations=_read_only_annotations("Title"))` stacked over `@flat_params(ParamsModel)`.
   Use `_write_annotations`, `_idempotent_write_annotations`, or `_destructive_write_annotations` for
   write operations
1. Call `self.get_client()` for the client and return a result. Read tools usually return a `str` through `truncate_response()`. Write tools and some other tools, such as `zammad_list_events`, return a Pydantic model
1. Add tests through the public FastMCP boundary with a mocked `ZammadClient`. See the
   `zammad_list_knowledge_bases` example in [CONTRIBUTING.md](CONTRIBUTING.md#1-new-tools)

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

```text
tests/
├── test_server.py          # Main test suite
├── conftest.py             # Shared fixtures
├── resilience_support.py   # Shared helpers for resilience tests
├── test_*.py               # Additional test modules
└── integration/            # Subprocess tests (HTTP transport, resilience over HTTP)
```

### Mock Strategy

- Mock `ZammadClient` for all tests
- Use factory fixtures for test data
- Parametrize for multiple scenarios
- Cover error paths explicitly

### Coverage Goals

- Enforced target: 86% overall coverage
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

- ~~Custom authentication providers~~ (implemented via Zammad Doorkeeper OAuth proxy)
- Additional ticket sources
- Workflow automation
- Custom prompts/tools

### Scalability

- Horizontal scaling with load balancer
- Distributed caching with Redis
- Message queue for async operations
- Database for audit logs
