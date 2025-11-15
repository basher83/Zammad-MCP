# MCP Audit Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix MCP protocol compliance issues, enhance documentation, and update to MCP 1.21.1 to resolve security vulnerability.

**Architecture:** Apply MCP best practices incrementally: fix naming, enhance docstrings with complete schemas, unify response formats, update dependencies, validate with tests.

**Tech Stack:** Python 3.13, FastMCP 1.21.1+, Pydantic v2, pytest

---

## Phase 1: Critical Fixes (30 minutes)

### Task 1.1: Fix Server Name

**Files:**
- Modify: `mcp_zammad/server.py:549`
- Test: `tests/test_server.py`

**Step 1: Write failing test for server name**

Add to `tests/test_server.py`:

```python
def test_server_name_follows_mcp_convention():
    """Server name must follow Python MCP convention: {service}_mcp."""
    server = ZammadMCPServer()
    # FastMCP stores name in mcp.name
    assert server.mcp.name == "zammad_mcp", (
        f"Expected 'zammad_mcp', got '{server.mcp.name}'. "
        "Python MCP servers must use lowercase with underscores."
    )
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_server.py::test_server_name_follows_mcp_convention -v
```

Expected: `FAIL` with assertion showing current name `"Zammad MCP Server"`

**Step 3: Fix server name**

In `mcp_zammad/server.py:549`, change:

```python
# Before
self.mcp = FastMCP("Zammad MCP Server", lifespan=self._create_lifespan())

# After
self.mcp = FastMCP("zammad_mcp", lifespan=self._create_lifespan())
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_server.py::test_server_name_follows_mcp_convention -v
```

Expected: `PASS`

**Step 5: Run full test suite**

```bash
uv run pytest --cov=mcp_zammad
```

Expected: All tests pass, coverage ≥ 90%

**Step 6: Commit**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "fix(server): change name to 'zammad_mcp' per MCP convention

Fixes server naming to follow Python MCP best practices.
Server names must use format: {service}_mcp (lowercase with underscores).

Ref: MCP best practices, Python implementation guide"
```

---

### Task 1.2: Simplify CHARACTER_LIMIT

**Files:**
- Modify: `mcp_zammad/server.py:73`
- Test: `tests/test_server.py`

**Step 1: Write test for character limit constant**

Add to `tests/test_server.py`:

```python
def test_character_limit_is_constant():
    """CHARACTER_LIMIT should be a module constant, not configurable."""
    from mcp_zammad.server import CHARACTER_LIMIT
    assert CHARACTER_LIMIT == 25000
    assert isinstance(CHARACTER_LIMIT, int)
```

**Step 2: Run test**

```bash
uv run pytest tests/test_server.py::test_character_limit_is_constant -v
```

Expected: `PASS` (validates current behavior)

**Step 3: Simplify CHARACTER_LIMIT**

In `mcp_zammad/server.py:73`, change:

```python
# Before
CHARACTER_LIMIT = int(os.getenv("ZAMMAD_MCP_CHARACTER_LIMIT", "25000"))  # Maximum response size in characters

# After
CHARACTER_LIMIT = 25000  # Maximum response size per MCP best practices
```

**Step 4: Remove os import if unused**

Check if `os` is still needed in `mcp_zammad/server.py`. If only used for CHARACTER_LIMIT, remove it from imports at top of file.

**Step 5: Run tests**

```bash
uv run pytest tests/test_server.py -v
```

Expected: All pass

**Step 6: Commit**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "refactor(server): simplify CHARACTER_LIMIT to constant

Remove environment variable override for CHARACTER_LIMIT.
MCP best practice is 25,000 characters - no need for configuration.

Simplifies setup and removes potential misconfiguration."
```

---

## Phase 2: Enhanced Documentation (3-4 hours)

### Task 2.1: Create Docstring Template Helper

**Files:**
- Create: `mcp_zammad/docstring_templates.py`
- Test: `tests/test_docstring_templates.py`

**Step 1: Write test for docstring template**

Create `tests/test_docstring_templates.py`:

```python
"""Tests for docstring template helpers."""
import pytest
from mcp_zammad.docstring_templates import format_tool_docstring


def test_format_tool_docstring_includes_all_sections():
    """Docstring template must include Args, Returns, Examples, Errors."""
    doc = format_tool_docstring(
        summary="Search for tickets",
        args_doc={
            "query": "Search string",
            "limit": "Maximum results (1-100)"
        },
        return_schema={
            "items": "list[Ticket]",
            "total": "int | None",
            "count": "int"
        },
        examples=[
            "Find open tickets: query='state:open'",
            "Search by number: query='#65003'"
        ],
        errors=[
            "Returns 'No tickets found' if no matches",
            "Returns 'Error: Rate limit' on 429 status"
        ]
    )

    assert "Args:" in doc
    assert "Returns:" in doc
    assert "Examples:" in doc
    assert "Errors:" in doc
    assert "query (str): Search string" in doc
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_docstring_templates.py::test_format_tool_docstring_includes_all_sections -v
```

Expected: `FAIL` - module doesn't exist

**Step 3: Create docstring template helper**

Create `mcp_zammad/docstring_templates.py`:

```python
"""Helper functions for generating MCP tool docstrings per best practices."""


def format_tool_docstring(
    summary: str,
    args_doc: dict[str, str],
    return_schema: dict[str, str],
    examples: list[str],
    errors: list[str],
    use_when: list[str] | None = None,
    dont_use_when: list[str] | None = None,
) -> str:
    """Format complete MCP tool docstring with all required sections.

    Args:
        summary: One-line tool description
        args_doc: Parameter name -> description mapping
        return_schema: Field name -> type description for return value
        examples: List of usage examples
        errors: List of error scenarios and messages
        use_when: Optional list of when to use this tool
        dont_use_when: Optional list of when NOT to use this tool

    Returns:
        Formatted docstring following MCP Python best practices
    """
    lines = [summary, ""]

    # Args section
    lines.append("Args:")
    for param, desc in args_doc.items():
        lines.append(f"    {param}: {desc}")
    lines.append("")

    # Returns section with schema
    lines.append("Returns:")
    lines.append("    Formatted string with the following schema:")
    lines.append("")
    lines.append("    {")
    for field, type_desc in return_schema.items():
        lines.append(f'        "{field}": {type_desc},')
    lines.append("    }")
    lines.append("")

    # Examples section
    if use_when or dont_use_when or examples:
        lines.append("Examples:")
        if use_when:
            for example in use_when:
                lines.append(f"    - Use when: {example}")
        if dont_use_when:
            for example in dont_use_when:
                lines.append(f"    - Don't use when: {example}")
        for example in examples:
            lines.append(f"    - {example}")
        lines.append("")

    # Error handling section
    if errors:
        lines.append("Error Handling:")
        for error in errors:
            lines.append(f"    - {error}")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_docstring_templates.py -v
```

Expected: `PASS`

**Step 5: Commit**

```bash
git add mcp_zammad/docstring_templates.py tests/test_docstring_templates.py
git commit -m "feat(docs): add docstring template helper

Create helper function to generate MCP-compliant tool docstrings.
Ensures all tools have consistent documentation with:
- Complete Args section with types
- Return schema examples
- Usage examples (when to use/not use)
- Error handling documentation

Ref: MCP Python implementation guide"
```

---

### Task 2.2: Add Title Annotations to All Tools

**Files:**
- Modify: `mcp_zammad/server.py:83-102`
- Test: `tests/test_server.py`

**Step 1: Write test for title annotations**

Add to `tests/test_server.py`:

```python
def test_all_tools_have_title_annotation():
    """All tools must have 'title' annotation for human-readable display."""
    server = ZammadMCPServer()

    # Get all registered tools (method depends on FastMCP API)
    # This is a placeholder - adjust based on actual FastMCP API
    tools = server.mcp.list_tools()

    for tool in tools:
        assert "title" in tool.annotations, (
            f"Tool '{tool.name}' missing 'title' annotation. "
            "Add title for better UX in MCP clients."
        )
        assert tool.annotations["title"], "Title must not be empty"
        # Title should be human-readable (not snake_case)
        assert " " in tool.annotations["title"], (
            f"Title '{tool.annotations['title']}' should be human-readable with spaces"
        )
```

**Step 2: Update annotation constants**

In `mcp_zammad/server.py`, modify the annotation constants to accept title parameter:

```python
# Before (lines 83-102)
_READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

# After - make helper functions instead
def _read_only_annotations(title: str) -> dict[str, Any]:
    """Create read-only tool annotations with title."""
    return {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
        "title": title,
    }

def _write_annotations(title: str) -> dict[str, Any]:
    """Create write tool annotations with title."""
    return {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
        "title": title,
    }

def _idempotent_write_annotations(title: str) -> dict[str, Any]:
    """Create idempotent write tool annotations with title."""
    return {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
        "title": title,
    }
```

**Step 3: Update first tool as example**

In `mcp_zammad/server.py:616`, update `zammad_search_tickets`:

```python
# Before
@self.mcp.tool(annotations=_READ_ONLY_ANNOTATIONS)
def zammad_search_tickets(params: TicketSearchParams) -> str:

# After
@self.mcp.tool(annotations=_read_only_annotations("Search Zammad Tickets"))
def zammad_search_tickets(params: TicketSearchParams) -> str:
```

**Step 4: Update remaining 17 tools**

Update all tool decorators with appropriate titles:

```python
# Ticket tools
@self.mcp.tool(annotations=_read_only_annotations("Get Ticket Details"))
def zammad_get_ticket(params: GetTicketParams) -> Ticket:

@self.mcp.tool(annotations=_write_annotations("Create New Ticket"))
def zammad_create_ticket(params: TicketCreate) -> Ticket:

@self.mcp.tool(annotations=_write_annotations("Update Ticket"))
def zammad_update_ticket(params: TicketUpdateParams) -> Ticket:

@self.mcp.tool(annotations=_write_annotations("Add Ticket Article"))
def zammad_add_article(params: ArticleCreate) -> Article:

@self.mcp.tool(annotations=_read_only_annotations("Get Article Attachments"))
def zammad_get_article_attachments(params: GetArticleAttachmentsParams) -> list[Attachment]:

@self.mcp.tool(annotations=_read_only_annotations("Download Attachment"))
def zammad_download_attachment(params: DownloadAttachmentParams) -> str:

@self.mcp.tool(annotations=_idempotent_write_annotations("Add Ticket Tag"))
def zammad_add_ticket_tag(params: TagOperationParams) -> TagOperationResult:

@self.mcp.tool(annotations=_idempotent_write_annotations("Remove Ticket Tag"))
def zammad_remove_ticket_tag(params: TagOperationParams) -> TagOperationResult:

# User & Organization tools
@self.mcp.tool(annotations=_read_only_annotations("Get User Details"))
def zammad_get_user(params: GetUserParams) -> User:

@self.mcp.tool(annotations=_read_only_annotations("Search Users"))
def zammad_search_users(params: SearchUsersParams) -> str:

@self.mcp.tool(annotations=_read_only_annotations("Get Organization Details"))
def zammad_get_organization(params: GetOrganizationParams) -> Organization:

@self.mcp.tool(annotations=_read_only_annotations("Search Organizations"))
def zammad_search_organizations(params: SearchOrganizationsParams) -> str:

@self.mcp.tool(annotations=_read_only_annotations("Get Current User"))
def zammad_get_current_user() -> User:

# System tools
@self.mcp.tool(annotations=_read_only_annotations("Get Ticket Statistics"))
def zammad_get_ticket_stats(params: GetTicketStatsParams) -> TicketStats:

@self.mcp.tool(annotations=_read_only_annotations("List Groups"))
def zammad_list_groups(params: ListParams) -> str:

@self.mcp.tool(annotations=_read_only_annotations("List Ticket States"))
def zammad_list_ticket_states(params: ListParams) -> str:

@self.mcp.tool(annotations=_read_only_annotations("List Ticket Priorities"))
def zammad_list_ticket_priorities(params: ListParams) -> str:
```

**Step 5: Run tests**

```bash
uv run pytest tests/test_server.py::test_all_tools_have_title_annotation -v
```

Expected: `PASS`

**Step 6: Run full test suite**

```bash
uv run pytest --cov=mcp_zammad
```

Expected: All pass, coverage ≥ 90%

**Step 7: Commit**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "feat(server): add title annotations to all tools

Add human-readable titles to all 18 MCP tools for better UX in clients.
Refactor annotation constants to helper functions that accept title parameter.

Titles follow pattern: '{Action} {Resource}' (e.g., 'Search Zammad Tickets')

Ref: MCP best practices - tool annotations"
```

---

### Task 2.3: Enhanced Docstrings - Search Tools

**Files:**
- Modify: `mcp_zammad/server.py:617-652`
- Test: `tests/test_server.py`

**Step 1: Update zammad_search_tickets docstring**

In `mcp_zammad/server.py:617-625`, replace docstring:

```python
@self.mcp.tool(annotations=_read_only_annotations("Search Zammad Tickets"))
def zammad_search_tickets(params: TicketSearchParams) -> str:
    """Search for tickets with filters and pagination.

    Args:
        params (TicketSearchParams): Validated search parameters containing:
            - query (Optional[str]): Search string (matches title, body, tags)
            - state (Optional[str]): Filter by state name (e.g., "open", "closed")
            - priority (Optional[str]): Filter by priority name (e.g., "high")
            - group (Optional[str]): Filter by group name
            - owner (Optional[str]): Filter by owner email/login
            - customer (Optional[str]): Filter by customer email/login
            - page (int): Page number (default: 1)
            - per_page (int): Results per page, 1-100 (default: 20)
            - response_format (ResponseFormat): Output format (default: MARKDOWN)

    Returns:
        str: Formatted response with the following schema:

        Markdown format (default):
        ```
        # Ticket Search Results: [filters]

        Found N ticket(s)

        ## Ticket #65003 - Title
        - **ID**: 123 (use this for get_ticket, NOT number)
        - **State**: open
        - **Priority**: high
        - **Created**: 2024-01-15T10:30:00Z
        ```

        JSON format:
        ```json
        {
            "items": [
                {
                    "id": 123,
                    "number": "65003",
                    "title": "string",
                    "state": {"id": 1, "name": "open"},
                    "priority": {"id": 2, "name": "high"},
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ],
            "total": null,
            "count": 20,
            "page": 1,
            "per_page": 20,
            "has_more": true,
            "next_page": 2,
            "next_offset": 20
        }
        ```

    Examples:
        - Use when: "Find all open tickets" -> state="open"
        - Use when: "Search for network issues" -> query="network"
        - Use when: "Tickets assigned to sarah" -> owner="sarah@company.com"
        - Don't use when: You have ticket ID (use zammad_get_ticket instead)

    Error Handling:
        - Returns "Found 0 ticket(s)" if no matches
        - Returns "Error: Rate limit exceeded" on 429 status
        - Returns "Error: Invalid authentication" on 401 status
        - May be truncated if results exceed 25,000 characters (use pagination)

    Note:
        Use the 'id' field from results for get_ticket, NOT the 'number' field.
        Example: Ticket #65003 may have id=123. Use id=123 for API calls.
    """
    client = self.get_client()
    # ... existing implementation
```

**Step 2: Run tests to verify no breakage**

```bash
uv run pytest tests/test_server.py -v -k search_tickets
```

Expected: All search_tickets tests pass

**Step 3: Commit**

```bash
git add mcp_zammad/server.py
git commit -m "docs(server): enhance zammad_search_tickets docstring

Add complete MCP-compliant documentation including:
- Full parameter descriptions with types and examples
- Complete return schema for both markdown and JSON formats
- Usage examples (when to use, when not to use)
- Error handling scenarios
- Important notes about ID vs number distinction

Ref: MCP Python implementation guide - tool documentation"
```

---

### Task 2.4: Enhanced Docstrings - Remaining Tools

**Files:**
- Modify: `mcp_zammad/server.py` (multiple tool functions)

**Step 1: Update zammad_get_ticket docstring**

Similar pattern - add complete schema, examples, error handling.

**Step 2: Update zammad_create_ticket docstring**

Include schema for ticket creation, validation errors.

**Step 3: Update remaining 15 tools**

Follow same pattern for:
- zammad_update_ticket
- zammad_add_article
- zammad_get_article_attachments
- zammad_download_attachment
- zammad_add_ticket_tag
- zammad_remove_ticket_tag
- zammad_get_user
- zammad_search_users
- zammad_get_organization
- zammad_search_organizations
- zammad_get_current_user
- zammad_get_ticket_stats
- zammad_list_groups
- zammad_list_ticket_states
- zammad_list_ticket_priorities

**Step 4: Run full test suite**

```bash
uv run pytest --cov=mcp_zammad
```

Expected: All pass, coverage ≥ 90%

**Step 5: Commit**

```bash
git add mcp_zammad/server.py
git commit -m "docs(server): enhance docstrings for all 18 tools

Add MCP-compliant documentation to all tools:
- Complete parameter descriptions with types
- Full return schemas (markdown and JSON formats)
- Usage examples and guidance
- Error handling scenarios
- Important notes and caveats

Improves LLM tool selection and usage accuracy.

Ref: MCP Python implementation guide - complete documentation"
```

---

## Phase 3: Response Format Unification (2-3 hours)

### Task 3.1: Add ResponseFormat to GetTicketParams

**Files:**
- Modify: `mcp_zammad/models.py`
- Test: `tests/test_models.py`

**Step 1: Write test for response_format parameter**

Add to `tests/test_models.py`:

```python
def test_get_ticket_params_has_response_format():
    """GetTicketParams should support response_format parameter."""
    params = GetTicketParams(
        ticket_id=123,
        response_format=ResponseFormat.JSON
    )
    assert params.response_format == ResponseFormat.JSON

    # Test default is MARKDOWN
    params_default = GetTicketParams(ticket_id=123)
    assert params_default.response_format == ResponseFormat.MARKDOWN
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_models.py::test_get_ticket_params_has_response_format -v
```

Expected: `FAIL` - GetTicketParams doesn't have response_format field

**Step 3: Add response_format to GetTicketParams**

In `mcp_zammad/models.py`, find GetTicketParams and add:

```python
class GetTicketParams(StrictBaseModel):
    """Parameters for getting a specific ticket."""

    ticket_id: int = Field(..., description="Ticket ID (internal database ID, not display number)")
    include_articles: bool = Field(default=False, description="Include ticket articles in response")
    article_limit: int = Field(default=50, ge=1, le=200, description="Maximum articles to return")
    article_offset: int = Field(default=0, ge=0, description="Article pagination offset")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: markdown (default) or json"
    )
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_models.py::test_get_ticket_params_has_response_format -v
```

Expected: `PASS`

**Step 5: Commit**

```bash
git add mcp_zammad/models.py tests/test_models.py
git commit -m "feat(models): add response_format to GetTicketParams

Add response_format parameter to GetTicketParams.
Default is MARKDOWN per MCP best practices.

Prep for unified response formatting across all tools."
```

---

### Task 3.2: Create Ticket Markdown Formatter

**Files:**
- Modify: `mcp_zammad/server.py`
- Test: `tests/test_server.py`

**Step 1: Write test for ticket detail formatter**

Add to `tests/test_server.py`:

```python
def test_format_ticket_detail_markdown(sample_ticket):
    """Test formatting single ticket as markdown."""
    from mcp_zammad.server import _format_ticket_detail_markdown

    result = _format_ticket_detail_markdown(sample_ticket)

    assert f"# Ticket #{sample_ticket.number}" in result
    assert f"**ID**: {sample_ticket.id}" in result
    assert f"**Title**: {sample_ticket.title}" in result
    assert "**State**:" in result
    assert "**Priority**:" in result
    assert "**Created**:" in result
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_server.py::test_format_ticket_detail_markdown -v
```

Expected: `FAIL` - function doesn't exist

**Step 3: Create _format_ticket_detail_markdown function**

Add to `mcp_zammad/server.py` near other format functions:

```python
def _format_ticket_detail_markdown(ticket: Ticket) -> str:
    """Format single ticket with full details as markdown.

    Args:
        ticket: Ticket object to format

    Returns:
        Markdown-formatted string
    """
    lines = [f"# Ticket #{ticket.number} - {ticket.title}", ""]
    lines.append(f"**ID**: {ticket.id}")
    lines.append(f"**State**: {_brief_field(ticket.state, 'name')}")
    lines.append(f"**Priority**: {_brief_field(ticket.priority, 'name')}")
    lines.append(f"**Group**: {_brief_field(ticket.group, 'name')}")
    lines.append(f"**Owner**: {_brief_field(ticket.owner, 'email')}")
    lines.append(f"**Customer**: {_brief_field(ticket.customer, 'email')}")
    lines.append(f"**Created**: {ticket.created_at.isoformat()}")
    lines.append(f"**Updated**: {ticket.updated_at.isoformat()}")
    lines.append("")

    # Tags
    if ticket.tags:
        lines.append(f"**Tags**: {', '.join(ticket.tags)}")
        lines.append("")

    # Articles
    if hasattr(ticket, 'articles') and ticket.articles:
        lines.append("## Articles")
        lines.append("")
        for i, article in enumerate(ticket.articles, 1):
            lines.append(f"### Article {i}")
            lines.append(f"- **From**: {article.get('from', 'Unknown')}")
            lines.append(f"- **Type**: {article.get('type', 'Unknown')}")
            lines.append(f"- **Created**: {article.get('created_at', 'Unknown')}")
            lines.append("")
            body = article.get('body', '')
            # Truncate very long bodies
            if len(body) > 500:
                body = body[:500] + "...\n(truncated)"
            lines.append(body)
            lines.append("")

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_server.py::test_format_ticket_detail_markdown -v
```

Expected: `PASS`

**Step 5: Commit**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "feat(server): add markdown formatter for ticket details

Create _format_ticket_detail_markdown for single ticket formatting.
Includes full metadata, tags, and articles with truncation.

Part of response format unification."
```

---

### Task 3.3: Update zammad_get_ticket to Support Response Format

**Files:**
- Modify: `mcp_zammad/server.py:655-681`
- Test: `tests/test_server.py`

**Step 1: Write test for get_ticket response formats**

Add to `tests/test_server.py`:

```python
def test_get_ticket_supports_markdown_format(zammad_server, mock_client):
    """zammad_get_ticket should return markdown when requested."""
    from mcp_zammad.models import GetTicketParams, ResponseFormat

    mock_client.get_ticket.return_value = {"id": 123, "number": "65003", "title": "Test"}

    params = GetTicketParams(ticket_id=123, response_format=ResponseFormat.MARKDOWN)
    result = zammad_server.zammad_get_ticket(params)

    assert isinstance(result, str)
    assert "# Ticket #" in result
    assert "**ID**: 123" in result


def test_get_ticket_supports_json_format(zammad_server, mock_client):
    """zammad_get_ticket should return JSON when requested."""
    from mcp_zammad.models import GetTicketParams, ResponseFormat
    import json

    mock_client.get_ticket.return_value = {"id": 123, "number": "65003", "title": "Test"}

    params = GetTicketParams(ticket_id=123, response_format=ResponseFormat.JSON)
    result = zammad_server.zammad_get_ticket(params)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["id"] == 123
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_server.py -k "test_get_ticket_supports" -v
```

Expected: `FAIL` - returns Ticket object, not formatted string

**Step 3: Update zammad_get_ticket return type and implementation**

In `mcp_zammad/server.py:654-681`, change:

```python
# Before
@self.mcp.tool(annotations=_read_only_annotations("Get Ticket Details"))
def zammad_get_ticket(params: GetTicketParams) -> Ticket:
    """..."""
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
        _handle_ticket_not_found_error(params.ticket_id, e)

# After
@self.mcp.tool(annotations=_read_only_annotations("Get Ticket Details"))
def zammad_get_ticket(params: GetTicketParams) -> str:
    """..."""
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

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_server.py -k "test_get_ticket_supports" -v
```

Expected: `PASS`

**Step 5: Run full test suite**

```bash
uv run pytest tests/test_server.py -v
```

Expected: May have some failures in tests expecting Ticket object. Fix those tests.

**Step 6: Update broken tests**

Find tests that expect `Ticket` object return from `zammad_get_ticket` and update them to parse the JSON/markdown string.

**Step 7: Commit**

```bash
git add mcp_zammad/server.py tests/test_server.py
git commit -m "feat(server): add response format support to zammad_get_ticket

Change return type from Ticket to str (formatted).
Support both markdown (default) and JSON formats.
Markdown provides human-readable output per MCP best practices.

Breaking change: Returns formatted string instead of Pydantic object."
```

---

### Task 3.4: Apply Same Pattern to User and Organization Tools

**Files:**
- Modify: `mcp_zammad/server.py` (user/org tools)
- Modify: `mcp_zammad/models.py` (param models)
- Test: `tests/test_server.py`

**Step 1: Add response_format to GetUserParams**

Similar to GetTicketParams.

**Step 2: Create _format_user_detail_markdown**

Format single user as markdown.

**Step 3: Update zammad_get_user**

Change return type to str, format based on response_format.

**Step 4: Repeat for Organization**

GetOrganizationParams, _format_organization_detail_markdown, zammad_get_organization.

**Step 5: Test and commit**

```bash
uv run pytest tests/test_server.py -v
git add mcp_zammad/server.py mcp_zammad/models.py tests/test_server.py
git commit -m "feat(server): unify response formats for user and org tools

Add response_format support to:
- zammad_get_user
- zammad_get_organization

All data-returning tools now support markdown (default) and JSON.

Completes response format unification per MCP best practices."
```

---

## Phase 4: MCP Package Update (30 minutes)

### Task 4.1: Update MCP Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Step 1: Check current MCP version**

```bash
uv pip list | grep mcp
```

Expected: Shows mcp 1.12.2

**Step 2: Update pyproject.toml**

In `pyproject.toml`, find dependencies section and update:

```toml
# Before
dependencies = [
    "mcp>=1.12.2",
    # ... other deps
]

# After
dependencies = [
    "mcp>=1.21.1",
    # ... other deps
]
```

**Step 3: Sync dependencies**

```bash
uv sync
```

Expected: Downloads and installs mcp 1.21.1 and updated dependencies (including patched starlette)

**Step 4: Verify starlette version**

```bash
uv pip list | grep starlette
```

Expected: starlette >= 0.49.1 (fixed CVE-2025-62727)

**Step 5: Run full test suite**

```bash
uv run pytest --cov=mcp_zammad -v
```

Expected: All tests pass with ≥ 90% coverage

**Step 6: Run quality checks**

```bash
./scripts/quality-check.sh
```

Expected: All checks pass (ruff, mypy)

**Step 7: Test manually with real Zammad instance**

```bash
# Set credentials in .env
uv run python -m mcp_zammad
```

Test a few tools interactively to ensure MCP 1.21.1 compatibility.

**Step 8: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build(deps): update mcp to 1.21.1 to fix starlette vulnerability

Update mcp from 1.12.2 to 1.21.1.
This resolves CVE-2025-62727 (starlette DoS vulnerability).

Changes:
- mcp: 1.12.2 -> 1.21.1
- starlette: 0.47.2 -> 0.49.1+ (transitive)

Tested: All 68 tests pass, 90%+ coverage maintained.

Fixes #115"
```

---

## Phase 5: Testing and Validation (1 hour)

### Task 5.1: Add Integration Tests for Response Formats

**Files:**
- Create: `tests/test_integration_response_formats.py`

**Step 1: Create integration test file**

```python
"""Integration tests for response format unification."""
import json
import pytest
from mcp_zammad.models import ResponseFormat, GetTicketParams
from mcp_zammad.server import ZammadMCPServer


@pytest.fixture
def server_with_mock_client(mock_zammad_client):
    """Server with mocked client for integration testing."""
    server = ZammadMCPServer()
    server.client = mock_zammad_client
    return server


class TestTicketResponseFormats:
    """Test ticket tools with both markdown and JSON formats."""

    def test_search_tickets_markdown(self, server_with_mock_client, sample_tickets):
        """Search tickets returns markdown by default."""
        # Setup mock
        # Call tool
        # Assert markdown format
        pass

    def test_search_tickets_json(self, server_with_mock_client, sample_tickets):
        """Search tickets can return JSON."""
        pass

    def test_get_ticket_markdown(self, server_with_mock_client, sample_ticket):
        """Get ticket returns markdown by default."""
        pass

    def test_get_ticket_json(self, server_with_mock_client, sample_ticket):
        """Get ticket can return JSON."""
        pass


class TestUserResponseFormats:
    """Test user tools with both formats."""
    # Similar tests for user tools
    pass


class TestOrganizationResponseFormats:
    """Test organization tools with both formats."""
    # Similar tests for org tools
    pass
```

**Step 2: Implement tests**

Fill in test implementations.

**Step 3: Run integration tests**

```bash
uv run pytest tests/test_integration_response_formats.py -v
```

Expected: All pass

**Step 4: Commit**

```bash
git add tests/test_integration_response_formats.py
git commit -m "test: add integration tests for response format unification

Comprehensive tests verifying all tools support markdown and JSON.
Tests cover tickets, users, organizations.

Ensures MCP best practices compliance."
```

---

### Task 5.2: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: Update README with response format info**

Add section about response formats:

```markdown
### Response Formats

All data-returning tools support two output formats:

- **Markdown** (default): Human-readable format optimized for LLM consumption
- **JSON**: Machine-readable format with complete metadata

Example:

```python
# Markdown (default)
zammad_search_tickets(query="network", response_format="markdown")

# JSON
zammad_search_tickets(query="network", response_format="json")
```
```

**Step 2: Update CLAUDE.md**

Update project-specific notes about MCP version, response formats.

**Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: update for response format unification and MCP 1.21.1

Document:
- Response format support (markdown/JSON)
- MCP 1.21.1 update
- Enhanced tool documentation

Users now have clear guidance on format options."
```

---

### Task 5.3: Final Validation

**Files:**
- All modified files

**Step 1: Run complete test suite**

```bash
uv run pytest --cov=mcp_zammad --cov-report=term-missing
```

Expected: All 80+ tests pass, coverage ≥ 90%

**Step 2: Run all quality checks**

```bash
./scripts/quality-check.sh
```

Expected: All pass (ruff format, ruff check, mypy)

**Step 3: Test with real Zammad instance**

Manually test key workflows:
- Search tickets (markdown and JSON)
- Get ticket details (both formats)
- Create/update ticket
- Search users/organizations

**Step 4: Run security scan**

```bash
uv run python scripts/uv/security-scan.py
```

Expected: No vulnerabilities (starlette should be fixed)

**Step 5: Build Docker image**

```bash
./scripts/docker-build.sh
```

Expected: Builds successfully

**Step 6: Generate coverage report**

```bash
uv run pytest --cov=mcp_zammad --cov-report=html
open htmlcov/index.html
```

Verify coverage is ≥ 90%

**Step 7: Create summary commit**

```bash
git log --oneline origin/main..HEAD
```

Review all commits from this plan.

---

## Phase 6: Cleanup and Documentation

### Task 6.1: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Run mise run changelog**

```bash
mise run changelog
```

This uses git-cliff to update unreleased section.

**Step 2: Review generated changelog**

Ensure all commits are categorized properly:
- fix: Bug fixes
- feat: New features
- docs: Documentation
- build: Dependencies
- refactor: Code improvements

**Step 3: Commit changelog**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): update for MCP audit fixes

Document all changes from MCP audit implementation:
- Server naming fix
- Enhanced documentation (18 tools)
- Response format unification
- MCP 1.21.1 update
- Security vulnerability fix"
```

---

### Task 6.2: Close Issue #115

**Files:**
- GitHub issue #115

**Step 1: Verify starlette fix**

```bash
uv pip list | grep starlette
```

Expected: starlette >= 0.49.1

**Step 2: Add closing comment to issue**

```bash
gh issue comment 115 --body "Fixed in PR #XXX

Starlette vulnerability (CVE-2025-62727) resolved by updating MCP package:
- mcp: 1.12.2 → 1.21.1
- starlette: 0.47.2 → 0.49.1 (transitive)

Verified with:
\`\`\`bash
uv pip list | grep starlette
# starlette 0.49.1
\`\`\`

All tests pass, no security vulnerabilities detected."
```

**Step 3: Close issue**

```bash
gh issue close 115 --comment "Resolved by updating to MCP 1.21.1"
```

---

## Success Criteria

- [ ] All 68+ tests pass
- [ ] Coverage ≥ 90%
- [ ] No security vulnerabilities (pip-audit clean)
- [ ] All quality checks pass (ruff, mypy)
- [ ] Server name follows MCP convention: `zammad_mcp`
- [ ] All 18 tools have complete docstrings with schemas
- [ ] All 18 tools have title annotations
- [ ] All data tools support markdown and JSON formats
- [ ] MCP package updated to 1.21.1
- [ ] Starlette updated to ≥ 0.49.1
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Issue #115 closed

---

## Estimated Time

- Phase 1: Critical Fixes - 30 minutes
- Phase 2: Enhanced Documentation - 3-4 hours
- Phase 3: Response Format Unification - 2-3 hours
- Phase 4: MCP Package Update - 30 minutes
- Phase 5: Testing and Validation - 1 hour
- Phase 6: Cleanup - 30 minutes

**Total: 8-10 hours**

---

## Notes

- Use TDD throughout (write test, run to fail, implement, run to pass, commit)
- Commit after each task completion
- Run full test suite before moving to next phase
- Keep markdown as default format per MCP best practices
- Ensure backward compatibility where possible
- Update tests when changing return types

**Required Sub-Skill:** Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan.
