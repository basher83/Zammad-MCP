"""Basic tests for Zammad MCP server."""

from unittest.mock import Mock, patch

import pytest

from mcp_zammad import server
from mcp_zammad.server import (
    _UNINITIALIZED,
    add_article,
    add_ticket_tag,
    create_ticket,
    get_ticket,
    get_user,
    initialize,
    mcp,
    remove_ticket_tag,
    search_tickets,
)

# ==================== FIXTURES ====================


@pytest.fixture
def reset_client():
    """Fixture to reset and restore the global client."""
    original_client = server.zammad_client
    yield
    server.zammad_client = original_client


@pytest.fixture
def mock_zammad_client():
    """Fixture that provides a properly initialized mock client."""
    with patch("mcp_zammad.server.ZammadClient") as mock_client_class:
        mock_instance = Mock()
        mock_instance.get_current_user.return_value = {
            "email": "test@example.com",
            "id": 1,
            "firstname": "Test",
            "lastname": "User",
        }
        mock_client_class.return_value = mock_instance
        yield mock_instance, mock_client_class


@pytest.fixture
def sample_user_data():
    """Provides sample user data for tests."""
    return {
        "id": 1,
        "email": "test@example.com",
        "firstname": "Test",
        "lastname": "User",
        "login": "testuser",
        "active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_organization_data():
    """Provides sample organization data for tests."""
    return {"id": 1, "name": "Test Organization", "active": True, "domain": "test.com"}


@pytest.fixture
def sample_ticket_data():
    """Provides sample ticket data for tests."""
    return {
        "id": 1,
        "number": "12345",
        "title": "Test Ticket",
        "group_id": 1,
        "state_id": 1,
        "priority_id": 2,
        "customer_id": 1,
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        # Include the expanded fields
        "state": {"id": 1, "name": "open", "state_type_id": 1},
        "priority": {"id": 2, "name": "2 normal"},
        "group": {"id": 1, "name": "Users"},
        "customer": {"id": 1, "email": "customer@example.com"},
    }


@pytest.fixture
def sample_article_data():
    """Provides sample article data for tests."""
    return {
        "id": 1,
        "ticket_id": 1,
        "body": "Test article",
        "type": "note",
        "sender": "Agent",
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def ticket_factory():
    """Factory fixture to create ticket data with custom values."""

    def _make_ticket(**kwargs):
        base_ticket = {
            "id": 1,
            "number": "12345",
            "title": "Test Ticket",
            "group_id": 1,
            "state_id": 1,
            "priority_id": 2,
            "customer_id": 1,
            "created_by_id": 1,
            "updated_by_id": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        # Update with any provided custom values
        base_ticket.update(kwargs)
        return base_ticket

    return _make_ticket


# ==================== BASIC TESTS ====================


@pytest.mark.asyncio
async def test_server_initialization(mock_zammad_client):
    """Test that the server initializes correctly without external dependencies."""
    mock_instance, _ = mock_zammad_client

    # Initialize the server with mocked client
    await initialize()

    # Verify the client was created and tested
    mock_instance.get_current_user.assert_called_once()

    # Test tools are registered
    tools = await mcp.list_tools()
    assert len(tools) > 0

    tool_names = [tool.name for tool in tools]
    expected_tools = [
        "search_tickets",
        "get_ticket",
        "create_ticket",
        "update_ticket",
        "add_article",
        "get_user",
        "search_users",
        "get_organization",
        "search_organizations",
        "list_groups",
        "list_ticket_states",
        "list_ticket_priorities",
        "get_ticket_stats",
        "add_ticket_tag",
        "remove_ticket_tag",
        "get_current_user",
    ]
    for tool in expected_tools:
        assert tool in tool_names


@pytest.mark.asyncio
async def test_prompts():
    """Test that prompts are registered."""
    prompts = await mcp.list_prompts()
    assert len(prompts) > 0

    prompt_names = [p.name for p in prompts]
    assert "analyze_ticket" in prompt_names
    assert "draft_response" in prompt_names
    assert "escalation_summary" in prompt_names


@pytest.mark.asyncio
async def test_initialization_failure():
    """Test that initialization handles failures gracefully."""
    with patch("mcp_zammad.server.ZammadClient") as mock_client_class:
        # Make the client initialization fail
        mock_client_class.side_effect = Exception("Connection failed")

        # Initialize should raise the exception
        with pytest.raises(Exception, match="Connection failed"):
            await initialize()


@pytest.mark.asyncio
async def test_tool_without_client(reset_client):
    """Test that tools fail gracefully when client is not initialized."""
    # Use the fixture to reset the client
    _ = reset_client

    # Reset the global client
    server.zammad_client = _UNINITIALIZED

    # Should raise RuntimeError when client is not initialized
    with pytest.raises(RuntimeError, match="Zammad client not initialized"):
        search_tickets()


# ==================== PARAMETRIZED TESTS ====================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,priority,expected_count",
    [
        ("open", None, 2),
        ("closed", None, 1),
        (None, "1 low", 1),
        (None, "3 high", 1),
        ("open", "2 normal", 1),
    ],
)
async def test_search_tickets_with_filters(mock_zammad_client, ticket_factory, state, priority, expected_count):
    """Test search_tickets with various filter combinations."""
    mock_instance, _ = mock_zammad_client

    # Create test data based on parameters
    tickets = [
        ticket_factory(
            id=1, state={"id": 1, "name": "open", "state_type_id": 1}, priority={"id": 2, "name": "2 normal"}
        ),
        ticket_factory(id=2, state={"id": 2, "name": "open", "state_type_id": 1}, priority={"id": 1, "name": "1 low"}),
        ticket_factory(
            id=3, state={"id": 3, "name": "closed", "state_type_id": 2}, priority={"id": 3, "name": "3 high"}
        ),
    ]

    # Filter tickets based on test parameters
    filtered_tickets = []
    for ticket in tickets:
        if state and ticket["state"]["name"] != state:
            continue
        if priority and ticket["priority"]["name"] != priority:
            continue
        filtered_tickets.append(ticket)

    mock_instance.search_tickets.return_value = filtered_tickets

    # Initialize and test
    await initialize()

    server.zammad_client = mock_instance

    result = search_tickets(state=state, priority=priority)

    assert len(result) == expected_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page,per_page",
    [
        (1, 10),
        (2, 25),
        (1, 50),
        (5, 100),
    ],
)
async def test_search_tickets_pagination(mock_zammad_client, sample_ticket_data, page, per_page):
    """Test search_tickets pagination parameters."""
    mock_instance, _ = mock_zammad_client

    mock_instance.search_tickets.return_value = [sample_ticket_data]

    await initialize()

    server.zammad_client = mock_instance

    search_tickets(page=page, per_page=per_page)

    # Verify pagination parameters were passed correctly
    mock_instance.search_tickets.assert_called_once()
    call_args = mock_instance.search_tickets.call_args[1]
    assert call_args["page"] == page
    assert call_args["per_page"] == per_page


# ==================== ERROR HANDLING TESTS ====================


@pytest.mark.asyncio
async def test_get_ticket_with_invalid_id(mock_zammad_client):
    """Test get_ticket with invalid ticket ID."""
    mock_instance, _ = mock_zammad_client

    # Simulate API error for invalid ID
    mock_instance.get_ticket.side_effect = Exception("Ticket not found")

    await initialize()

    server.zammad_client = mock_instance

    with pytest.raises(Exception, match="Ticket not found"):
        get_ticket(ticket_id=99999)


@pytest.mark.asyncio
async def test_create_ticket_with_invalid_data(mock_zammad_client):
    """Test create_ticket with invalid data."""
    mock_instance, _ = mock_zammad_client

    # Simulate validation error
    mock_instance.create_ticket.side_effect = ValueError("Invalid customer email")

    await initialize()

    server.zammad_client = mock_instance

    with pytest.raises(ValueError, match="Invalid customer email"):
        create_ticket(title="Test", group="InvalidGroup", customer="not-an-email", article_body="Test")


@pytest.mark.asyncio
async def test_search_with_malformed_response(mock_zammad_client):
    """Test handling of malformed API responses."""
    mock_instance, _ = mock_zammad_client

    # Return malformed data (missing required fields)
    mock_instance.search_tickets.return_value = [
        {
            "id": 1,
            "title": "Incomplete Ticket",
            # Missing required fields like group_id, state_id, etc.
        }
    ]

    await initialize()

    server.zammad_client = mock_instance

    # Should raise validation error due to missing fields
    # Using a more specific exception would be better, but we're catching the general Exception
    # that gets raised when Pydantic validation fails
    with pytest.raises((ValueError, TypeError)):  # More specific than general Exception
        search_tickets()


# ==================== TOOL SPECIFIC TESTS ====================


@pytest.mark.asyncio
async def test_search_tickets_tool(mock_zammad_client, sample_ticket_data):
    """Test the search_tickets tool with mocked client."""
    mock_instance, _ = mock_zammad_client

    # Return complete ticket data that matches the model
    mock_instance.search_tickets.return_value = [sample_ticket_data]

    # Initialize the server
    await initialize()

    # Ensure we're using the mocked client
    server.zammad_client = mock_instance

    result = search_tickets(state="open")

    # Verify the result
    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].title == "Test Ticket"

    # Verify the mock was called correctly
    mock_instance.search_tickets.assert_called_once_with(
        query=None, state="open", priority=None, group=None, owner=None, customer=None, page=1, per_page=25
    )


@pytest.mark.asyncio
async def test_get_ticket_tool(mock_zammad_client, sample_ticket_data, sample_article_data):
    """Test the get_ticket tool with mocked client."""
    mock_instance, _ = mock_zammad_client

    # Complete ticket data with articles
    mock_ticket_data = {**sample_ticket_data, "articles": [sample_article_data]}
    mock_instance.get_ticket.return_value = mock_ticket_data

    # Initialize the server
    await initialize()

    server.zammad_client = mock_instance

    result = get_ticket(ticket_id=1, include_articles=True)

    # Verify the result
    assert result.id == 1
    assert result.title == "Test Ticket"
    assert result.articles is not None
    assert len(result.articles) == 1

    # Verify the mock was called correctly
    mock_instance.get_ticket.assert_called_once_with(1, True, 10, 0)


@pytest.mark.asyncio
async def test_create_ticket_tool(mock_zammad_client, ticket_factory):
    """Test the create_ticket tool with mocked client."""
    mock_instance, _ = mock_zammad_client

    # Mock response for created ticket
    created_ticket_data = ticket_factory(
        id=2,
        number="12346",
        title="New Test Ticket",
        created_at="2024-01-02T00:00:00Z",
        updated_at="2024-01-02T00:00:00Z",
    )
    mock_instance.create_ticket.return_value = created_ticket_data

    # Initialize the server
    await initialize()

    server.zammad_client = mock_instance

    result = create_ticket(
        title="New Test Ticket", group="Support", customer="customer@example.com", article_body="Test article body"
    )

    # Verify the result
    assert result.id == created_ticket_data["id"]
    assert result.title == "New Test Ticket"

    # Verify the mock was called correctly
    mock_instance.create_ticket.assert_called_once_with(
        title="New Test Ticket",
        group="Support",
        customer="customer@example.com",
        article_body="Test article body",
        state="new",
        priority="2 normal",
        article_type="note",
        article_internal=False,
    )


@pytest.mark.asyncio
async def test_add_article_tool(mock_zammad_client, sample_article_data):
    """Test the add_article tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.add_article.return_value = sample_article_data

    await initialize()

    server.zammad_client = mock_instance

    result = add_article(ticket_id=1, body="New comment", article_type="note", internal=False)

    assert result.body == "Test article"
    assert result.type == "note"

    mock_instance.add_article.assert_called_once_with(
        ticket_id=1, body="New comment", article_type="note", internal=False, sender="Agent"
    )


@pytest.mark.asyncio
async def test_get_user_tool(mock_zammad_client, sample_user_data):
    """Test the get_user tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.get_user.return_value = sample_user_data

    await initialize()

    server.zammad_client = mock_instance

    result = get_user(user_id=1)

    assert result.id == 1
    assert result.email == "test@example.com"

    mock_instance.get_user.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_tag_operations(mock_zammad_client):
    """Test add and remove tag operations."""
    mock_instance, _ = mock_zammad_client

    mock_instance.add_ticket_tag.return_value = {"success": True}
    mock_instance.remove_ticket_tag.return_value = {"success": True}

    await initialize()

    server.zammad_client = mock_instance

    # Test adding tag
    add_result = add_ticket_tag(ticket_id=1, tag="urgent")
    assert add_result["success"] is True
    mock_instance.add_ticket_tag.assert_called_once_with(1, "urgent")

    # Test removing tag
    remove_result = remove_ticket_tag(ticket_id=1, tag="urgent")
    assert remove_result["success"] is True
    mock_instance.remove_ticket_tag.assert_called_once_with(1, "urgent")
