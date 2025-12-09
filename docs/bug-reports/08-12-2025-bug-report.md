# Bug Report: Ticket Creation Issues

**Date**: 2025-12-08
**Related Issues**: #148, #149
**Reporter**: @Erudition
**Severity**: High (blocks core functionality)

---

## Issue #148: Inconsistent `article_type` convention causes ticket creation tool failure

### Summary

The `zammad_create_ticket` tool docstring incorrectly describes parameter structure, causing LLMs to generate invalid API calls that fail Pydantic validation.

### Error Message

```
params.article_body Field required
params.article Extra inputs are not permitted
```

### Root Cause Analysis

**Phase 1: Data Flow Trace**

The data flows through three components with a mismatch:

| Component | Expected Structure |
|-----------|-------------------|
| **Docstring** (server.py:1054) | `article (dict): Initial article with body and type` |
| **Pydantic Model** (models.py:256-266) | Flat fields: `article_body`, `article_type`, `article_internal` |
| **Client** (client.py:197-207) | Constructs nested `article` dict internally |

**What LLM sees:** The docstring says `article` is a dict, so LLM sends:
```json
{"article": {"body": "...", "type": "note"}}
```

**What Pydantic expects:** Flat fields:
```json
{"article_body": "...", "article_type": "note"}
```

**Result:** Pydantic rejects `article` as extra input and requires `article_body`.

**Phase 2: Pattern Analysis**

Comparing with `zammad_add_article` tool (server.py:1155-1162):

| Aspect | create_ticket | add_article |
|--------|---------------|-------------|
| Model field | `article_type: str` | `article_type: ArticleType` |
| Alias | None | `alias="type"` |
| Type | Plain string | Enum |
| Docstring accuracy | **INCORRECT** | Correct |

The add_article docstring correctly documents `article_type (ArticleType)` as a parameter.

**Additional Docstring Errors (server.py:1050-1058):**

Line 1054: Says `article (dict)` - WRONG, should be `article_body`, `article_type`, `article_internal`
Line 1057: Lists `owner` parameter - DOESN'T EXIST in TicketCreate model
Line 1058: Lists `tags` parameter - DOESN'T EXIST in TicketCreate model
Lines 1077-1078: Examples reference `article` - Should reference `article_body`
Lines 1088-1089: Note mentions "article parameter" - Should mention `article_body`

### Recommended Fix

Update `server.py` docstring (lines 1046-1092) to match actual Pydantic model:

```python
"""Create a new ticket in Zammad with initial article.

Args:
    params (TicketCreate): Validated ticket creation parameters containing:
        - title (str): Ticket title/subject (required)
        - group (str): Group name to assign ticket (required)
        - customer (str): Customer email or login (required)
        - article_body (str): Initial article/comment content (required)
        - article_type (str): Article type - note, email, phone (default: "note")
        - article_internal (bool): Whether article is internal (default: False)
        - state (str): State name (default: "new")
        - priority (str): Priority name (default: "2 normal")

...

Examples:
    - Use when: "Create ticket for server outage" -> title, group, customer, article_body
    - Use when: "New high priority ticket" -> add priority="3 high"

...

Note:
    The article content goes in article_body. The article_type defaults to "note"
    but can be "email" or "phone" for different communication types.
```

### Affected Files

- `mcp_zammad/server.py:1046-1092` - Docstring needs complete rewrite

### Fix Complexity

**Low** - Documentation-only change, no code logic changes required.

---

## Issue #149: Cannot create ticket unless customer exists

### Summary

Ticket creation fails when the specified customer email doesn't exist in Zammad, with no way to create the customer first.

### Error Message

```json
{
  "error": "No lookup value found for 'customer': \"mike.johnson@real.com\"",
  "error_human": "No lookup value found for 'customer': \"mike.johnson@real.com\""
}
```

### Root Cause Analysis

**Phase 1: Data Flow Trace**

1. User calls `zammad_create_ticket(customer="new@example.com", ...)`
2. MCP server passes `customer` to `client.create_ticket()`
3. Client builds: `{"customer": "new@example.com", ...}`
4. Zammad API attempts to lookup customer by email
5. Customer doesn't exist → Zammad returns error
6. Error propagates back unchanged

**Phase 2: Zammad API Behavior**

Per [Zammad community discussion](https://community.zammad.org/t/auto-create-user-from-ticket-api/6850):

- Zammad API does NOT auto-create customers during ticket creation
- This is by design - customers must exist before ticket creation
- The `guess:` prefix syntax was discussed but not implemented

**Phase 3: Available Workarounds**

Current MCP tools:
- `zammad_search_users` - Can search for existing users
- `zammad_get_user` - Can get user by ID
- **No `zammad_create_user` tool exists**

The zammad-py library supports `client.user.create(params)` but this capability is not exposed via MCP.

### Two Issues Identified

**Issue A: Missing Feature**
No `zammad_create_user` tool exists, preventing the standard workflow:
1. Check if customer exists (`zammad_search_users`)
2. If not, create customer (`zammad_create_user`) ← MISSING
3. Create ticket with customer

**Issue B: Non-Actionable Error Message**
Current error from Zammad is passed through unchanged:
```
No lookup value found for 'customer': "mike.johnson@real.com"
```

Per [error-handling-guide.md](/.claude/skills/zammad-mcp-quality/references/error-handling-guide.md), this should be:
```
Error: Customer "mike.johnson@real.com" not found in Zammad.
Note: Customers must exist before creating tickets.
How to fix: Use zammad_search_users to find existing customers, or use zammad_create_user to create a new customer first.
Example: zammad_create_user(email="mike.johnson@real.com", firstname="Mike", lastname="Johnson")
```

### Recommended Fix

**Fix A: Add `zammad_create_user` tool**

1. Add to `client.py`:
```python
def create_user(
    self,
    email: str,
    firstname: str | None = None,
    lastname: str | None = None,
    **kwargs
) -> dict[str, Any]:
    """Create a new user/customer."""
    user_data = {"email": email}
    if firstname:
        user_data["firstname"] = firstname
    if lastname:
        user_data["lastname"] = lastname
    user_data.update(kwargs)
    return dict(self.api.user.create(params=user_data))
```

2. Add to `models.py`:
```python
class UserCreate(StrictBaseModel):
    """Create user request."""
    email: str = Field(description="User email address (required)")
    firstname: str | None = Field(None, description="First name")
    lastname: str | None = Field(None, description="Last name")
    organization: str | None = Field(None, description="Organization name")
    phone: str | None = Field(None, description="Phone number")
```

3. Add to `server.py`:
```python
@self.mcp.tool(annotations=_write_annotations("Create User"))
def zammad_create_user(params: UserCreate) -> User:
    """Create a new user/customer in Zammad.

    Args:
        params: User creation parameters containing:
            - email (str): User email address (required)
            - firstname (str | None): First name
            - lastname (str | None): Last name
            - organization (str | None): Organization name

    Note:
        Users are typically created as customers. Use this tool before
        creating tickets for new customers.
    """
    client = self.get_client()
    user_data = client.create_user(**params.model_dump(exclude_none=True))
    return User(**user_data)
```

**Fix B: Improve error message in create_ticket**

Wrap the API call to catch and improve the error:

```python
try:
    ticket_data = client.create_ticket(**params.model_dump(exclude_none=True, mode="json"))
except Exception as e:
    if "No lookup value found for 'customer'" in str(e):
        raise ValueError(
            f"Error: Customer '{params.customer}' not found in Zammad. "
            f"Note: Customers must exist before creating tickets. "
            f"How to fix: Use zammad_search_users to find existing customers, "
            f"or use zammad_create_user to create a new customer first."
        ) from e
    raise
```

### Affected Files

- `mcp_zammad/client.py` - Add `create_user` method
- `mcp_zammad/models.py` - Add `UserCreate` model
- `mcp_zammad/server.py` - Add `zammad_create_user` tool, improve error handling

### Fix Complexity

**Medium** - Requires new tool implementation and tests.

---

## Summary

| Issue | Type | Root Cause | Fix |
|-------|------|------------|-----|
| #148 | Documentation bug | Docstring describes wrong parameter structure | Update docstring to match Pydantic model |
| #149 | Missing feature + Poor error message | No create_user tool; error not actionable | Add zammad_create_user tool; improve error message |

### Priority Recommendation

1. **Fix #148 first** - Simple docstring fix, immediate improvement for all users
2. **Fix #149 second** - Requires new tool, but essential for real-world usage

### References

- [Zammad User API Documentation](https://docs.zammad.org/en/latest/api/user.html)
- [zammad-py Library](https://github.com/joeirimpan/zammad_py)
- [Zammad Community Discussion on Auto-Create](https://community.zammad.org/t/auto-create-user-from-ticket-api/6850)
- [Error Handling Guide](/.claude/skills/zammad-mcp-quality/references/error-handling-guide.md)

---

**Created by**: Claude Code
**Last Updated**: 2025-12-08
**Investigation Method**: Systematic debugging with data flow tracing
