# Fix GitHub Issues #148 and #149 - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix ticket creation bugs - incorrect docstring (#148) and missing create_user tool (#149)

**Architecture:** Two independent fixes - docstring-only update for #148, new tool + error handling for #149

**Tech Stack:** Python 3.13, FastMCP, Pydantic, pytest

---

## Plan 1: Fix #148 - Docstring Correction (~15 min)

### Task 1.1: Update `zammad_create_ticket` Docstring

**File:** `mcp_zammad/server.py:1045-1096`

**Problem:** Docstring says `article (dict)` but model uses flat `article_body`, `article_type`, `article_internal`. Also mentions non-existent `owner` and `tags` params.

**Replace lines 1047-1092 with:**

```python
"""Create a new ticket in Zammad with initial article.

Args:
    params (TicketCreate): Validated ticket creation parameters containing:
        - title (str): Ticket title/subject (required)
        - group (str): Group name to assign ticket (required)
        - customer (str): Customer email or login (required, must exist in Zammad)
        - article_body (str): Initial article/comment body (required)
        - state (str): State name (default: "new")
        - priority (str): Priority name (default: "2 normal")
        - article_type (str): Article type - "note", "email", "phone" (default: "note")
        - article_internal (bool): Whether article is internal-only (default: False)

Returns:
    Ticket: The created ticket object with schema:

        {
            "id": 124,
            "number": "65004",
            "title": "New issue",
            "state": {"id": 1, "name": "new"},
            "priority": {"id": 2, "name": "2 normal"},
            "customer": {"id": 5, "email": "user@example.com"},
            "group": {"id": 3, "name": "Support"},
            "created_at": "2024-01-15T15:00:00Z"
        }

Examples:
    - Use when: "Create ticket for server outage" -> title, group, customer, article_body
    - Use when: "New high priority ticket" -> add priority="3 high"
    - Don't use when: Ticket already exists (use zammad_update_ticket)
    - Don't use when: Only adding comment (use zammad_add_article)

Error Handling:
    - Returns "Error: Validation failed" if required fields missing
    - Returns "Error: Permission denied" if no create permissions
    - Returns "Error: Resource not found" if group/customer/state invalid

Note:
    The customer must exist in Zammad before creating a ticket.
    Use zammad_create_user to create new customers first.
"""
```

### Task 1.2: Run Quality Checks

```bash
uv run ruff format mcp_zammad && uv run ruff check mcp_zammad && uv run pytest -v -k "create_ticket"
```

### Task 1.3: Commit

```bash
git add mcp_zammad/server.py
git commit -m "fix(docs): correct zammad_create_ticket docstring (#148)"
```

---

## Plan 2: Fix #149 - Add `zammad_create_user` Tool (~45 min)

### Task 2.1: Write Test for `UserCreate` Model

**File:** `tests/test_server.py` (add after model tests ~line 2400)

```python
def test_user_create_model_validation():
    """Test UserCreate model validates required fields."""
    from pydantic import ValidationError
    from mcp_zammad.models import UserCreate

    # Valid user
    user = UserCreate(email="new@example.com", firstname="New", lastname="User")
    assert user.email == "new@example.com"

    # Missing required field
    with pytest.raises(ValidationError):
        UserCreate(firstname="Missing", lastname="Email")
```

**Run:** `uv run pytest tests/test_server.py::test_user_create_model_validation -v`
**Expected:** FAIL - ImportError

### Task 2.2: Create `UserCreate` Model

**File:** `mcp_zammad/models.py` (add after line 519)

```python
class UserCreate(StrictBaseModel):
    """Create user request."""

    email: str = Field(description="User email (required)", max_length=255)
    firstname: str = Field(description="First name", max_length=100)
    lastname: str = Field(description="Last name", max_length=100)
    login: str | None = Field(None, description="Login username", max_length=255)
    phone: str | None = Field(None, description="Phone number", max_length=100)
    mobile: str | None = Field(None, description="Mobile number", max_length=100)
    organization: str | None = Field(None, description="Organization name", max_length=255)
    note: str | None = Field(None, description="Internal notes", max_length=5000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError(f"Invalid email: '{v}'. Example: user@example.com")
        return v.lower().strip()

    @field_validator("firstname", "lastname")
    @classmethod
    def sanitize_names(cls, v: str) -> str:
        return html.escape(v)
```

**Run:** `uv run pytest tests/test_server.py::test_user_create_model_validation -v`
**Expected:** PASS

### Task 2.3: Write Test for Client Method

**File:** `tests/test_client_methods.py` (add in user section ~line 140)

```python
def test_create_user(self, mock_zammad_api: Mock) -> None:
    mock_instance = mock_zammad_api.return_value
    mock_instance.user.create.return_value = {
        "id": 42, "email": "new@example.com", "firstname": "New", "lastname": "User"
    }

    client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test")
    result = client.create_user(email="new@example.com", firstname="New", lastname="User")

    assert result["id"] == 42
    mock_instance.user.create.assert_called_once()
```

**Run:** `uv run pytest tests/test_client_methods.py::TestZammadClient::test_create_user -v`
**Expected:** FAIL - AttributeError

### Task 2.4: Implement Client Method

**File:** `mcp_zammad/client.py` (add after line 306)

```python
def create_user(
    self,
    email: str,
    firstname: str,
    lastname: str,
    login: str | None = None,
    phone: str | None = None,
    mobile: str | None = None,
    organization: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Create a new user in Zammad."""
    user_data: dict[str, Any] = {"email": email, "firstname": firstname, "lastname": lastname}
    if login: user_data["login"] = login
    if phone: user_data["phone"] = phone
    if mobile: user_data["mobile"] = mobile
    if organization: user_data["organization"] = organization
    if note: user_data["note"] = note
    return dict(self.api.user.create(user_data))
```

**Run:** `uv run pytest tests/test_client_methods.py::TestZammadClient::test_create_user -v`
**Expected:** PASS

### Task 2.5: Write Test for MCP Tool

**File:** `tests/test_server.py` (add after user tool tests ~line 930)

```python
def test_create_user_tool(mock_zammad_client, decorator_capturer):
    """Test zammad_create_user tool."""
    mock_instance, _ = mock_zammad_client
    mock_instance.create_user.return_value = {
        "id": 42, "email": "new@example.com", "firstname": "New", "lastname": "User",
        "active": True, "created_at": "2024-01-15T10:00:00Z", "updated_at": "2024-01-15T10:00:00Z"
    }

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool
    server_inst.get_client = lambda: server_inst.client
    server_inst._setup_tools()

    from mcp_zammad.models import UserCreate
    params = UserCreate(email="new@example.com", firstname="New", lastname="User")
    result = test_tools["zammad_create_user"](params)

    assert result.id == 42
```

**Run:** `uv run pytest tests/test_server.py::test_create_user_tool -v`
**Expected:** FAIL - KeyError

### Task 2.6: Implement MCP Tool

**File:** `mcp_zammad/server.py`

**Step A:** Add import (line ~54):
```python
from .models import (..., UserCreate)
```

**Step B:** Add tool (after `zammad_search_users` ~line 1598):

```python
@self.mcp.tool(annotations=_write_annotations("Create User"))
def zammad_create_user(params: UserCreate) -> User:
    """Create a new user (customer) in Zammad.

    Args:
        params (UserCreate): User creation parameters:
            - email (str): Email address (required)
            - firstname (str): First name (required)
            - lastname (str): Last name (required)
            - login, phone, mobile, organization, note (optional)

    Returns:
        User: Created user object

    Examples:
        - "Create customer" -> email, firstname, lastname
        - "Add contact with phone" -> + phone field
        - Don't use when: User exists (use zammad_search_users first)

    Note:
        After creating, use their email in zammad_create_ticket's customer field.
    """
    client = self.get_client()
    user_data = client.create_user(**params.model_dump(exclude_none=True))
    return User(**user_data)
```

**Run:** `uv run pytest tests/test_server.py -k "create_user" -v`
**Expected:** PASS

### Task 2.7: Add Error Handling for Customer Not Found

**File:** `mcp_zammad/server.py:1093-1096`

**Replace:**
```python
client = self.get_client()
ticket_data = client.create_ticket(**params.model_dump(exclude_none=True, mode="json"))
return Ticket(**ticket_data)
```

**With:**
```python
client = self.get_client()
try:
    ticket_data = client.create_ticket(**params.model_dump(exclude_none=True, mode="json"))
    return Ticket(**ticket_data)
except Exception as e:
    error_msg = str(e).lower()
    if "customer" in error_msg and ("not found" in error_msg or "couldn't find" in error_msg or "lookup" in error_msg):
        raise ValueError(
            f"Customer '{params.customer}' not found in Zammad. "
            f"Note: Customers must exist before creating tickets. "
            f"Use zammad_search_users to check, or zammad_create_user to create. "
            f"Example: zammad_create_user(email='{params.customer}', firstname='...', lastname='...')"
        ) from e
    raise
```

### Task 2.8: Test Error Message

**File:** `tests/test_server.py`

```python
def test_create_ticket_customer_not_found_error(mock_zammad_client, decorator_capturer):
    mock_instance, _ = mock_zammad_client
    mock_instance.create_ticket.side_effect = Exception("No lookup value found for 'customer'")

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool
    server_inst.get_client = lambda: server_inst.client
    server_inst._setup_tools()

    from mcp_zammad.models import TicketCreate
    params = TicketCreate(title="Test", group="Support", customer="new@example.com", article_body="Body")

    with pytest.raises(ValueError) as exc_info:
        test_tools["zammad_create_ticket"](params)

    assert "zammad_create_user" in str(exc_info.value)
```

### Task 2.9: Run Full Quality Checks

```bash
uv run ruff format mcp_zammad tests
uv run ruff check mcp_zammad tests
uv run mypy mcp_zammad
uv run pytest --cov=mcp_zammad
```

### Task 2.10: Commit

```bash
git add mcp_zammad/ tests/
git commit -m "feat: add zammad_create_user tool (#149)"
```

---

## Critical Files

| File | Changes |
|------|---------|
| `mcp_zammad/server.py` | Fix docstring (1047-1092), add tool (~1598), add error handling (1093) |
| `mcp_zammad/models.py` | Add UserCreate class (after line 519) |
| `mcp_zammad/client.py` | Add create_user method (after line 306) |
| `tests/test_server.py` | Add 3 new tests |
| `tests/test_client_methods.py` | Add 1 new test |

---

## Execution Choice

**Option 1: Subagent-Driven** - Fresh subagent per task, review between, fast iteration
**Option 2: Sequential** - Execute tasks in order manually
