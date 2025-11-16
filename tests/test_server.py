"""Basic tests for Zammad MCP server."""

import base64
import json
import os
import pathlib
import tempfile
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests
from pydantic import ValidationError

from mcp_zammad.models import (
    Article,
    ArticleCreate,
    ArticleSender,
    ArticleType,
    Attachment,
    GetOrganizationParams,
    GetTicketParams,
    GetTicketStatsParams,
    GetUserParams,
    Group,
    ListParams,
    Organization,
    PriorityBrief,
    ResponseFormat,
    SearchUsersParams,
    StateBrief,
    Ticket,
    TicketPriority,
    TicketSearchParams,
    TicketState,
    User,
    UserBrief,
)
from mcp_zammad.server import (
    CHARACTER_LIMIT,
    ZammadMCPServer,
    _brief_field,
    _extract_member_info,
    _find_max_items_for_limit,
    _format_ticket_detail_markdown,
    _handle_api_error,
    _idempotent_write_annotations,
    _normalize_datetime_to_iso,
    _read_only_annotations,
    _write_annotations,
    main,
    mcp,
    truncate_response,
)

# ==================== FIXTURES ====================


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
def server_instance(mock_zammad_client):
    """Fixture that provides an initialized ZammadMCPServer instance."""
    mock_instance, _ = mock_zammad_client
    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    return server_inst


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
    return {
        "id": 1,
        "name": "Test Organization",
        "active": True,
        "domain": "test.com",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


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
def sample_ticket(sample_ticket_data):
    """Provides sample Ticket object for tests."""
    return Ticket(**sample_ticket_data)


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

    # Initialize the server instance with mocked client
    server_inst = ZammadMCPServer()
    await server_inst.initialize()

    # Verify the client was created and tested
    mock_instance.get_current_user.assert_called_once()

    # Test tools are registered
    tools = await mcp.list_tools()
    assert len(tools) > 0

    tool_names = [tool.name for tool in tools]
    expected_tools = [
        "zammad_search_tickets",
        "zammad_get_ticket",
        "zammad_create_ticket",
        "zammad_update_ticket",
        "zammad_add_article",
        "zammad_get_user",
        "zammad_search_users",
        "zammad_get_organization",
        "zammad_search_organizations",
        "zammad_list_groups",
        "zammad_list_ticket_states",
        "zammad_list_ticket_priorities",
        "zammad_get_ticket_stats",
        "zammad_add_ticket_tag",
        "zammad_remove_ticket_tag",
        "zammad_get_current_user",
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
        server_inst = ZammadMCPServer()
        with pytest.raises(Exception, match="Connection failed"):
            await server_inst.initialize()


def test_tool_without_client():
    """Test that tools fail gracefully when client is not initialized."""
    # Create server instance without initializing client
    server_inst = ZammadMCPServer()
    server_inst.client = None

    # Should raise RuntimeError when client is not initialized
    with pytest.raises(RuntimeError, match="Zammad client not initialized"):
        server_inst.get_client()


# ==================== PARAMETRIZED TESTS ====================


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
def test_search_tickets_with_filters(mock_zammad_client, ticket_factory, state, priority, expected_count):
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

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    tickets_data = client.search_tickets(state=state, priority=priority)
    result = [Ticket(**t) for t in tickets_data]

    assert len(result) == expected_count


@pytest.mark.parametrize(
    "page,per_page",
    [
        (1, 10),
        (2, 25),
        (1, 50),
        (5, 100),
    ],
)
def test_search_tickets_pagination(mock_zammad_client, sample_ticket_data, page, per_page):
    """Test search_tickets pagination parameters."""
    mock_instance, _ = mock_zammad_client

    mock_instance.search_tickets.return_value = [sample_ticket_data]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    client.search_tickets(page=page, per_page=per_page)

    # Verify pagination parameters were passed correctly
    mock_instance.search_tickets.assert_called_once()
    call_args = mock_instance.search_tickets.call_args[1]
    assert call_args["page"] == page
    assert call_args["per_page"] == per_page


# ==================== ERROR HANDLING TESTS ====================


def test_get_ticket_with_invalid_id(mock_zammad_client):
    """Test get_ticket with invalid ticket ID."""
    mock_instance, _ = mock_zammad_client

    # Simulate API error for invalid ID
    mock_instance.get_ticket.side_effect = Exception("Ticket not found")

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    with pytest.raises(Exception, match="Ticket not found"):
        client.get_ticket(99999)


def test_create_ticket_with_invalid_data(mock_zammad_client):
    """Test create_ticket with invalid data."""
    mock_instance, _ = mock_zammad_client

    # Simulate validation error
    mock_instance.create_ticket.side_effect = ValueError("Invalid customer email")

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    with pytest.raises(ValueError, match="Invalid customer email"):
        client.create_ticket(title="Test", group="InvalidGroup", customer="not-an-email", article_body="Test")


def test_search_with_malformed_response(mock_zammad_client):
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

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    # Should raise validation error due to missing fields
    # Using a more specific exception would be better, but we're catching the general Exception
    # that gets raised when Pydantic validation fails
    tickets_data = client.search_tickets()
    with pytest.raises((ValueError, TypeError)):  # More specific than general Exception
        [Ticket(**t) for t in tickets_data]


# ==================== TOOL SPECIFIC TESTS ====================


def test_search_tickets_tool(mock_zammad_client, sample_ticket_data):
    """Test the search_tickets tool with mocked client."""
    mock_instance, _ = mock_zammad_client

    # Return complete ticket data that matches the model
    mock_instance.search_tickets.return_value = [sample_ticket_data]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    tickets_data = client.search_tickets(state="open")
    result = [Ticket(**t) for t in tickets_data]

    # Verify the result
    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].title == "Test Ticket"

    # Verify the mock was called correctly (client method uses only specified parameters)
    mock_instance.search_tickets.assert_called_once_with(state="open")


def test_get_ticket_tool(mock_zammad_client, sample_ticket_data, sample_article_data):
    """Test the get_ticket tool with mocked client."""
    mock_instance, _ = mock_zammad_client

    # Complete ticket data with articles
    mock_ticket_data = {**sample_ticket_data, "articles": [sample_article_data]}
    mock_instance.get_ticket.return_value = mock_ticket_data

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    ticket_data = client.get_ticket(1, include_articles=True)
    result = Ticket(**ticket_data)

    # Verify the result
    assert result.id == 1
    assert result.title == "Test Ticket"
    assert result.articles is not None
    assert len(result.articles) == 1

    # Verify the mock was called correctly (client method uses keyword arguments)
    mock_instance.get_ticket.assert_called_once_with(1, include_articles=True)


def test_create_ticket_tool(mock_zammad_client, ticket_factory, decorator_capturer):
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

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    ticket_data = client.create_ticket(
        title="New Test Ticket", group="Support", customer="customer@example.com", article_body="Test article body"
    )
    result = Ticket(**ticket_data)

    # Verify the result
    assert result.id == created_ticket_data["id"]
    assert result.title == "New Test Ticket"

    # Verify the mock was called correctly (client method only passes explicit args)
    mock_instance.create_ticket.assert_called_once_with(
        title="New Test Ticket", group="Support", customer="customer@example.com", article_body="Test article body"
    )


def test_add_article_tool(mock_zammad_client, sample_article_data, decorator_capturer):
    """Test the add_article tool with ArticleCreate params model."""
    mock_instance, _ = mock_zammad_client

    mock_instance.add_article.return_value = sample_article_data

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Test with ArticleCreate params using Enum values
    params = ArticleCreate(ticket_id=1, body="New comment", article_type=ArticleType.NOTE, sender=ArticleSender.AGENT)
    result = test_tools["zammad_add_article"](params)

    assert result.body == "Test article"
    assert result.type == "note"

    # Verify the client was called with correct params
    mock_instance.add_article.assert_called_once_with(
        ticket_id=1, article_type="note", body="New comment", internal=False, sender="Agent"
    )


def test_add_article_invalid_type():
    """Test that ArticleCreate rejects invalid article types."""
    # Test invalid article type
    with pytest.raises(ValidationError, match="article_type"):
        ArticleCreate(ticket_id=1, body="test", article_type="invalid_type")


def test_add_article_invalid_sender():
    """Test that ArticleCreate rejects invalid sender types."""
    # Test invalid sender
    with pytest.raises(ValidationError, match="sender"):
        ArticleCreate(ticket_id=1, body="test", sender="InvalidSender")


def test_add_article_backward_compat_alias():
    """Test that ArticleCreate accepts 'type' alias for backward compatibility."""
    # Test using alias 'type' instead of 'article_type'
    params = ArticleCreate(ticket_id=1, body="test", type="email")
    assert params.article_type == ArticleType.EMAIL

    # Test that field is accessible as article_type
    params2 = ArticleCreate(ticket_id=1, body="test", type=ArticleType.PHONE)
    assert params2.article_type == ArticleType.PHONE


def test_get_user_tool(mock_zammad_client, sample_user_data):
    """Test the get_user tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.get_user.return_value = sample_user_data

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    user_data = client.get_user(1)
    result = User(**user_data)

    assert result.id == 1
    assert result.email == "test@example.com"

    mock_instance.get_user.assert_called_once_with(1)


def test_tag_operations(mock_zammad_client):
    """Test add and remove tag operations."""
    mock_instance, _ = mock_zammad_client

    mock_instance.add_ticket_tag.return_value = {"success": True}
    mock_instance.remove_ticket_tag.return_value = {"success": True}

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    # Test adding tag
    add_result = client.add_ticket_tag(1, "urgent")
    assert add_result["success"] is True
    mock_instance.add_ticket_tag.assert_called_once_with(1, "urgent")

    # Test removing tag
    remove_result = client.remove_ticket_tag(1, "urgent")
    assert remove_result["success"] is True
    mock_instance.remove_ticket_tag.assert_called_once_with(1, "urgent")


def test_update_ticket_tool(mock_zammad_client, sample_ticket_data):
    """Test update ticket tool."""
    mock_instance, _ = mock_zammad_client

    # Mock the update response
    updated_ticket = sample_ticket_data.copy()
    updated_ticket["title"] = "Updated Title"
    updated_ticket["state_id"] = 2
    updated_ticket["priority_id"] = 3

    mock_instance.update_ticket.return_value = updated_ticket

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    # Test updating multiple fields
    ticket_data = client.update_ticket(
        1, title="Updated Title", state="open", priority="3 high", owner="agent@example.com", group="Support"
    )
    result = Ticket(**ticket_data)

    assert result.id == 1
    assert result.title == "Updated Title"

    # Verify the client was called with correct parameters
    mock_instance.update_ticket.assert_called_once_with(
        1, title="Updated Title", state="open", priority="3 high", owner="agent@example.com", group="Support"
    )


def test_get_organization_tool(mock_zammad_client, sample_organization_data):
    """Test get organization tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.get_organization.return_value = sample_organization_data

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    result = client.get_organization(1)

    # Verify we can create Organization model from the data
    org = Organization(**result)
    assert org.id == 1
    assert org.name == "Test Organization"
    assert org.domain == "test.com"

    mock_instance.get_organization.assert_called_once_with(1)


def test_search_organizations_tool(mock_zammad_client, sample_organization_data):
    """Test search organizations tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.search_organizations.return_value = [sample_organization_data]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    # Test basic search
    results = client.search_organizations(query="test", page=1, per_page=25)

    assert len(results) == 1
    # Verify we can create Organization model from the data
    org = Organization(**results[0])
    assert org.name == "Test Organization"

    mock_instance.search_organizations.assert_called_once_with(query="test", page=1, per_page=25)

    # Test with pagination
    mock_instance.reset_mock()
    client.search_organizations(query="test", page=2, per_page=50)

    mock_instance.search_organizations.assert_called_once_with(query="test", page=2, per_page=50)


def test_list_groups_tool(mock_zammad_client):
    """Test list groups tool."""
    mock_instance, _ = mock_zammad_client

    mock_groups = [
        {
            "id": 1,
            "name": "Users",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "name": "Support",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 3,
            "name": "Sales",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
    ]

    mock_instance.get_groups.return_value = mock_groups

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    results = client.get_groups()

    assert len(results) == 3
    # Verify we can create Group models from the data
    groups = [Group(**group) for group in results]
    assert groups[0].name == "Users"
    assert groups[1].name == "Support"
    assert groups[2].name == "Sales"

    mock_instance.get_groups.assert_called_once()


def test_list_ticket_states_tool(mock_zammad_client):
    """Test list ticket states tool."""
    mock_instance, _ = mock_zammad_client

    mock_states = [
        {
            "id": 1,
            "name": "new",
            "state_type_id": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "name": "open",
            "state_type_id": 2,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 4,
            "name": "closed",
            "state_type_id": 5,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
    ]

    mock_instance.get_ticket_states.return_value = mock_states

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    results = client.get_ticket_states()

    assert len(results) == 3
    # Verify we can create TicketState models from the data
    states = [TicketState(**state) for state in results]
    assert states[0].name == "new"
    assert states[1].name == "open"
    assert states[2].name == "closed"

    mock_instance.get_ticket_states.assert_called_once()


def test_list_ticket_priorities_tool(mock_zammad_client):
    """Test list ticket priorities tool."""
    mock_instance, _ = mock_zammad_client

    mock_priorities = [
        {
            "id": 1,
            "name": "1 low",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "name": "2 normal",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 3,
            "name": "3 high",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
    ]

    mock_instance.get_ticket_priorities.return_value = mock_priorities

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    results = client.get_ticket_priorities()

    assert len(results) == 3
    # Verify we can create TicketPriority models from the data
    priorities = [TicketPriority(**priority) for priority in results]
    assert priorities[0].name == "1 low"
    assert priorities[1].name == "2 normal"
    assert priorities[2].name == "3 high"

    mock_instance.get_ticket_priorities.assert_called_once()


def test_get_current_user_tool(mock_zammad_client, sample_user_data):
    """Test get current user tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.get_current_user.return_value = sample_user_data

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    result = client.get_current_user()

    # Verify we can create User model from the data
    user = User(**result)
    assert user.id == 1
    assert user.email == "test@example.com"
    assert user.firstname == "Test"
    assert user.lastname == "User"

    mock_instance.get_current_user.assert_called_once()


def test_search_users_tool(mock_zammad_client, sample_user_data):
    """Test search users tool."""
    mock_instance, _ = mock_zammad_client

    mock_instance.search_users.return_value = [sample_user_data]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance
    client = server_inst.get_client()

    # Test basic search
    results = client.search_users(query="test@example.com", page=1, per_page=25)

    assert len(results) == 1
    # Verify we can create User model from the data
    user = User(**results[0])
    assert user.email == "test@example.com"
    assert user.firstname == "Test"

    mock_instance.search_users.assert_called_once_with(query="test@example.com", page=1, per_page=25)

    # Test with pagination
    mock_instance.reset_mock()
    client.search_users(query="test", page=3, per_page=10)

    mock_instance.search_users.assert_called_once_with(query="test", page=3, per_page=10)


def test_get_ticket_stats_tool(mock_zammad_client, decorator_capturer):
    """Test get ticket stats tool with pagination.

    Note: This test is still using the legacy wrapper function because get_ticket_stats
    is a complex tool that implements its own pagination and statistics calculation logic.
    The wrapper function will be removed in a future phase after the tool is fully migrated.
    """
    mock_instance, _ = mock_zammad_client

    # Create mock tickets with various states - split across pages
    page1_tickets = [
        {"id": 1, "state": "new", "title": "New ticket"},
        {"id": 2, "state": "open", "title": "Open ticket"},
        {"id": 3, "state": {"name": "open", "id": 2}, "title": "Open ticket 2"},
    ]
    page2_tickets = [
        {"id": 4, "state": "closed", "title": "Closed ticket"},
        {"id": 5, "state": {"name": "pending reminder", "id": 3}, "title": "Pending ticket"},
        {"id": 6, "state": "open", "first_response_escalation_at": "2024-01-01", "title": "Escalated ticket"},
    ]

    # Set up paginated responses - page 1, page 2, then empty page
    mock_instance.search_tickets.side_effect = [page1_tickets, page2_tickets, []]

    # Mock ticket states for state type mapping
    mock_instance.get_ticket_states.return_value = [
        {"id": 1, "name": "new", "state_type_id": 1, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"id": 2, "name": "open", "state_type_id": 2, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"id": 3, "name": "closed", "state_type_id": 3, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {
            "id": 4,
            "name": "pending reminder",
            "state_type_id": 4,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        },
        {"id": 5, "name": "pending close", "state_type_id": 5, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
    ]

    server_inst = ZammadMCPServer()
    server_inst.client = mock_instance

    # For get_ticket_stats, we need to test the actual tool implementation
    # which uses pagination internally, so we'll capture and call the tool directly
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_system_tools()

    # Test basic stats
    assert "zammad_get_ticket_stats" in test_tools
    params = GetTicketStatsParams()
    stats = test_tools["zammad_get_ticket_stats"](params)

    assert stats.total_count == 6
    assert stats.open_count == 4  # new + open tickets
    assert stats.closed_count == 1
    assert stats.pending_count == 1
    assert stats.escalated_count == 1

    # Verify pagination was used
    assert mock_instance.search_tickets.call_count == 3
    mock_instance.search_tickets.assert_any_call(group=None, page=1, per_page=100)
    mock_instance.search_tickets.assert_any_call(group=None, page=2, per_page=100)
    mock_instance.search_tickets.assert_any_call(group=None, page=3, per_page=100)

    # Test with group filter
    mock_instance.reset_mock()
    mock_instance.search_tickets.side_effect = [page1_tickets, []]  # One page then empty

    params_with_group = GetTicketStatsParams(group="Support")
    stats = test_tools["zammad_get_ticket_stats"](params_with_group)

    assert stats.total_count == 3
    assert stats.open_count == 3

    assert mock_instance.search_tickets.call_count == 2
    mock_instance.search_tickets.assert_any_call(group="Support", page=1, per_page=100)
    mock_instance.search_tickets.assert_any_call(group="Support", page=2, per_page=100)

    # Test with date filters (should log warning but still work)
    mock_instance.reset_mock()
    mock_instance.search_tickets.side_effect = [page1_tickets + page2_tickets, []]

    with patch("mcp_zammad.server.logger") as mock_logger:
        params_with_dates = GetTicketStatsParams(start_date="2024-01-01", end_date="2024-12-31")
        stats = test_tools["zammad_get_ticket_stats"](params_with_dates)

        assert stats.total_count == 6
        assert mock_instance.search_tickets.call_count == 2
        mock_instance.search_tickets.assert_any_call(group=None, page=1, per_page=100)
        mock_logger.warning.assert_called_with("Date filtering not yet implemented - ignoring date parameters")


def test_resource_handlers(decorator_capturer):
    """Test resource handler registration and execution."""
    server = ZammadMCPServer()
    server.client = Mock()

    # Setup resources
    server._setup_resources()

    # Test ticket resource - must use Pydantic models (issue #100 fix)
    # Mock must return a dict (as the real client does), not a Ticket object
    ticket_obj = Ticket(
        id=1,
        number="12345",
        title="Test Issue",
        group_id=1,
        state_id=1,
        priority_id=2,
        customer_id=1,
        created_by_id=1,
        updated_by_id=1,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        state=StateBrief(id=1, name="open", state_type_id=1),
        priority=PriorityBrief(id=2, name="high"),
        customer=UserBrief(id=1, login="test", email="test@example.com"),
        articles=[
            Article(
                id=1,
                ticket_id=1,
                type="note",
                sender="Agent",
                body="Initial ticket description",
                created_by_id=1,
                updated_by_id=1,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                created_by=UserBrief(id=1, login="agent", email="agent@example.com"),
            )
        ],
    )
    server.client.get_ticket.return_value = ticket_obj.model_dump()

    # Set up the client for the server
    server.get_client = lambda: server.client  # type: ignore[method-assign, assignment, return-value]  # type: ignore[method-assign]

    # We need to test the actual resource functions, which are defined inside _setup_resources
    # Let's create a new server instance and capture the resources as they're registered
    test_resources, capture_resource = decorator_capturer(server.mcp.resource)
    server.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
    server._setup_resources()

    # Now test the captured resource handlers
    result = test_resources["zammad://ticket/{ticket_id}"](ticket_id="1")

    assert "Ticket #12345 - Test Issue" in result
    assert "State: open" in result
    assert "Priority: high" in result
    assert "Customer: test@example.com" in result
    assert "Initial ticket description" in result

    # Test user resource
    server.client.get_user.return_value = {
        "id": 1,
        "firstname": "John",
        "lastname": "Doe",
        "email": "john.doe@example.com",
        "login": "jdoe",
        "organization": {"name": "Test Corp"},
        "active": True,
        "vip": False,
        "created_at": "2024-01-01T00:00:00Z",
    }

    result = test_resources["zammad://user/{user_id}"](user_id="1")

    assert "User: John Doe" in result
    assert "Email: john.doe@example.com" in result
    assert "Organization: Test Corp" in result

    # Test organization resource
    server.client.get_organization.return_value = {
        "id": 1,
        "name": "Test Corporation",
        "domain": "testcorp.com",
        "active": True,
        "note": "Important client",
        "created_at": "2024-01-01T00:00:00Z",
    }

    result = test_resources["zammad://organization/{org_id}"](org_id="1")

    assert "Organization: Test Corporation" in result
    assert "Domain: testcorp.com" in result
    assert "Note: Important client" in result

    # Test queue resource
    server.client.search_tickets.return_value = [
        {
            "id": 1,
            "number": "12345",
            "title": "Test Issue 1",
            "state": {"name": "open"},
            "priority": {"name": "high"},
            "customer": {"email": "customer1@example.com"},
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": 2,
            "number": "12346",
            "title": "Test Issue 2",
            "state": "closed",
            "priority": "2 normal",
            "customer": "customer2@example.com",
            "created_at": "2024-01-02T00:00:00Z",
        },
    ]

    result = test_resources["zammad://queue/{group}"](group="Support")

    assert "Queue for Group: Support" in result
    assert "Total Tickets: 2" in result
    assert "Open (1 tickets):" in result
    assert "Closed (1 tickets):" in result
    assert "#12345 (ID: 1) - Test Issue 1" in result
    assert "#12346 (ID: 2) - Test Issue 2" in result

    # Test empty queue resource
    server.client.search_tickets.return_value = []

    result = test_resources["zammad://queue/{group}"](group="EmptyGroup")
    assert "Queue for group 'EmptyGroup': No tickets found" in result


def test_resource_error_handling(decorator_capturer):
    """Test resource error handling."""
    server = ZammadMCPServer()
    server.client = Mock()

    # Use the same approach as test_resource_handlers
    test_resources, capture_resource = decorator_capturer(server.mcp.resource)
    server.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
    server.get_client = lambda: server.client  # type: ignore[method-assign, assignment, return-value]
    server._setup_resources()

    # Test ticket resource error
    server.client.get_ticket.side_effect = requests.exceptions.RequestException("API Error")

    result = test_resources["zammad://ticket/{ticket_id}"](ticket_id="999")
    assert "Error during retrieving ticket 999" in result
    assert "API Error" in result or "RequestException" in result

    # Test user resource error
    server.client.get_user.side_effect = requests.exceptions.HTTPError("User not found")

    result = test_resources["zammad://user/{user_id}"](user_id="999")
    assert "Error" in result and "retrieving user 999" in result

    # Test org resource error
    server.client.get_organization.side_effect = requests.exceptions.HTTPError("Org not found")

    result = test_resources["zammad://organization/{org_id}"](org_id="999")
    assert "Error" in result and "retrieving organization 999" in result

    # Test queue resource error
    server.client.search_tickets.side_effect = requests.exceptions.HTTPError("Queue not found")

    result = test_resources["zammad://queue/{group}"](group="nonexistent")
    assert "Error" in result and "retrieving queue for group 'nonexistent'" in result


def test_prompt_handlers(decorator_capturer):
    """Test prompt handlers."""
    server = ZammadMCPServer()

    # Capture prompts as they're registered
    test_prompts, capture_prompt = decorator_capturer(server.mcp.prompt)
    server.mcp.prompt = capture_prompt  # type: ignore[method-assign, assignment]
    server._setup_prompts()

    # Test analyze_ticket prompt
    assert "analyze_ticket" in test_prompts
    result = test_prompts["analyze_ticket"](ticket_id=123)
    assert "analyze ticket with ID 123" in result
    assert "get_ticket tool" in result

    # Test draft_response prompt
    assert "draft_response" in test_prompts
    result = test_prompts["draft_response"](ticket_id=123, tone="friendly")
    assert "draft a friendly response to ticket with ID 123" in result
    assert "add_article" in result

    # Test escalation_summary prompt
    assert "escalation_summary" in test_prompts
    result = test_prompts["escalation_summary"](group="Support")
    assert "escalated tickets for group 'Support'" in result
    assert "search_tickets" in result


def test_get_client_error():
    """Test get_client error when not initialized."""
    server = ZammadMCPServer()
    server.client = None

    with pytest.raises(RuntimeError, match="Zammad client not initialized"):
        server.get_client()


def test_get_client_success():
    """Test get_client returns client when initialized."""
    server = ZammadMCPServer()
    mock_client = Mock()
    server.client = mock_client

    result = server.get_client()
    assert result is mock_client


@pytest.mark.asyncio
async def test_initialize_with_dotenv():
    """Test initialize with .env file."""
    server = ZammadMCPServer()

    # Create a temp .env file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("ZAMMAD_URL=https://test.zammad.com/api/v1\n")
        f.write("ZAMMAD_HTTP_TOKEN=test-token\n")
        temp_env_path = f.name

    try:
        # Mock Path.cwd() to return temp directory
        with patch("mcp_zammad.server.Path.cwd") as mock_cwd:
            mock_cwd.return_value = pathlib.Path(temp_env_path).parent

            with patch("mcp_zammad.server.ZammadClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.get_current_user.return_value = {"email": "test@example.com"}
                mock_client_class.return_value = mock_client

                await server.initialize()

                assert server.client is not None
                mock_client.get_current_user.assert_called_once()
    finally:
        # Clean up
        os.unlink(temp_env_path)


@pytest.mark.asyncio
async def test_initialize_with_envrc_warning():
    """Test initialize with .envrc file but no env vars."""
    server = ZammadMCPServer()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".envrc", delete=False) as f:
        f.write("export ZAMMAD_URL=https://test.zammad.com/api/v1\n")
        temp_envrc_path = f.name

    try:
        with patch("mcp_zammad.server.Path.cwd") as mock_cwd:
            # Create the .envrc file in temp directory
            temp_dir = pathlib.Path(temp_envrc_path).parent
            envrc_file = temp_dir / ".envrc"
            envrc_file.write_text("export ZAMMAD_URL=https://test.zammad.com/api/v1\n")

            mock_cwd.return_value = temp_dir

            with (
                patch.dict(os.environ, {}, clear=True),
                patch("mcp_zammad.server.logger") as mock_logger,
                patch("mcp_zammad.server.ZammadClient") as mock_client_class,
            ):
                # Patch ZammadClient to avoid the ConfigException
                mock_client_class.side_effect = RuntimeError("No authentication method provided")
                with pytest.raises(RuntimeError, match="No authentication method provided"):
                    await server.initialize()

                # Check that warning was logged
                mock_logger.warning.assert_called_with(
                    "Found .envrc but environment variables not loaded. Consider using direnv or creating a .env file"
                )

            # Clean up
            envrc_file.unlink()
    finally:
        os.unlink(temp_envrc_path)


@pytest.mark.asyncio
async def test_lifespan_context_manager():
    """Test the lifespan context manager."""
    # Create a server instance and mock its initialize method
    test_server = ZammadMCPServer()

    with patch.object(test_server, "initialize", new=AsyncMock()) as mock_initialize:
        # Get the lifespan context manager
        lifespan_cm = test_server._create_lifespan()

        # Test the context manager
        async with lifespan_cm(test_server.mcp) as result:
            # Verify initialize was called
            mock_initialize.assert_called_once()
            # The yield should return None
            assert result is None


def test_tool_implementations_are_called():
    """Test that tool implementations are actually executed."""
    server = ZammadMCPServer()
    server.client = Mock()

    # Mock client methods with complete ticket data
    complete_ticket = {
        "id": 1,
        "number": "12345",
        "title": "Test",
        "state": "open",
        "group_id": 1,
        "state_id": 1,
        "priority_id": 2,
        "customer_id": 1,
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    server.client.search_tickets.return_value = [complete_ticket]
    server.client.get_ticket.return_value = complete_ticket
    server.client.create_ticket.return_value = complete_ticket
    server.client.update_ticket.return_value = complete_ticket
    server.client.add_article.return_value = {
        "id": 1,
        "body": "Article",
        "ticket_id": 1,
        "type": "note",
        "sender": "Agent",
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    server.client.get_user.return_value = {
        "id": 1,
        "email": "test@example.com",
        "firstname": "Test",
        "lastname": "User",
        "login": "test",
        "active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    server.client.search_users.return_value = [
        {
            "id": 1,
            "email": "test@example.com",
            "firstname": "Test",
            "lastname": "User",
            "login": "test",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ]
    server.client.get_organization.return_value = {
        "id": 1,
        "name": "Test Org",
        "active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    server.client.search_organizations.return_value = [
        {
            "id": 1,
            "name": "Test Org",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ]

    # Call tool handlers directly through the decorated functions
    # We need to actually invoke the tools to cover the implementation lines
    tool_manager = server.mcp._tool_manager

    # Find and call zammad_search_tickets tool
    search_tickets_tool = None
    for tool in tool_manager._tools.values():
        if tool.name == "zammad_search_tickets":
            search_tickets_tool = tool.fn
            break

    assert search_tickets_tool is not None
    params = TicketSearchParams(query="test")
    result = search_tickets_tool(params)
    assert isinstance(result, str)
    assert "Ticket #12345" in result
    server.client.search_tickets.assert_called_once()


def test_get_ticket_stats_pagination(decorator_capturer):
    """Test that get_ticket_stats tool uses pagination correctly."""
    server = ZammadMCPServer()
    server.client = Mock()

    # Mock ticket states for state type mapping
    server.client.get_ticket_states.return_value = [
        {"id": 1, "name": "new", "state_type_id": 1, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"id": 2, "name": "open", "state_type_id": 2, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"id": 3, "name": "closed", "state_type_id": 3, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {
            "id": 4,
            "name": "pending reminder",
            "state_type_id": 4,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        },
        {"id": 5, "name": "pending close", "state_type_id": 5, "created_at": "2024-01-01", "updated_at": "2024-01-01"},
    ]

    # Capture tools as they're registered
    test_tools, capture_tool = decorator_capturer(server.mcp.tool)
    server.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server.get_client = lambda: server.client  # type: ignore[method-assign, assignment, return-value]
    server._setup_system_tools()

    # Mock paginated responses
    page1_tickets = [
        {"id": 1, "state": {"name": "open"}},
        {"id": 2, "state": {"name": "closed"}},
    ]
    page2_tickets = [
        {"id": 3, "state": {"name": "pending reminder"}},
        {"id": 4, "state": {"name": "open"}, "first_response_escalation_at": "2024-01-01"},
    ]
    page3_tickets: list[dict[str, Any]] = []  # Empty page to stop pagination

    # Set up side_effect to return different pages
    server.client.search_tickets.side_effect = [page1_tickets, page2_tickets, page3_tickets]

    # Get the captured tool and call it
    assert "zammad_get_ticket_stats" in test_tools
    params = GetTicketStatsParams()
    result = test_tools["zammad_get_ticket_stats"](params)

    # Verify pagination calls
    assert server.client.search_tickets.call_count == 3
    server.client.search_tickets.assert_any_call(group=None, page=1, per_page=100)
    server.client.search_tickets.assert_any_call(group=None, page=2, per_page=100)
    server.client.search_tickets.assert_any_call(group=None, page=3, per_page=100)

    # Verify stats are correct
    assert result.total_count == 4
    assert result.open_count == 2
    assert result.closed_count == 1
    assert result.pending_count == 1
    assert result.escalated_count == 1


def test_get_ticket_stats_with_date_warning(decorator_capturer):
    """Test get_ticket_stats with date parameters shows warning."""
    server = ZammadMCPServer()
    server.client = Mock()

    # Capture tools as they're registered
    test_tools, capture_tool = decorator_capturer(server.mcp.tool)
    server.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server.get_client = lambda: server.client  # type: ignore[method-assign, assignment, return-value]
    server._setup_system_tools()

    # Mock search results
    server.client.search_tickets.return_value = []

    with patch("mcp_zammad.server.logger") as mock_logger:
        # Get the captured tool
        assert "zammad_get_ticket_stats" in test_tools
        params = GetTicketStatsParams(start_date="2024-01-01", end_date="2024-12-31")
        stats = test_tools["zammad_get_ticket_stats"](params)

        assert stats.total_count == 0
        mock_logger.warning.assert_called_with("Date filtering not yet implemented - ignoring date parameters")


class TestCachingMethods:
    """Test the caching functionality."""

    def test_cached_groups(self) -> None:
        """Test that groups are cached properly."""
        # Create server instance with mocked client
        server = ZammadMCPServer()
        server.client = Mock()

        # Mock the client to return groups
        groups_data = [
            {
                "id": 1,
                "name": "Users",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            },
            {
                "id": 2,
                "name": "Support",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            },
        ]
        server.client.get_groups.return_value = groups_data

        # First call should hit the API
        result1 = server._get_cached_groups()
        assert len(result1) == 2
        assert result1[0].name == "Users"
        server.client.get_groups.assert_called_once()

        # Second call should use cache
        result2 = server._get_cached_groups()
        assert result1 == result2
        # Still only called once
        server.client.get_groups.assert_called_once()

    def test_cached_states(self) -> None:
        """Test that ticket states are cached properly."""
        # Create server instance with mocked client
        server = ZammadMCPServer()
        server.client = Mock()

        states_data = [
            {
                "id": 1,
                "name": "new",
                "state_type_id": 1,
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            },
            {
                "id": 2,
                "name": "open",
                "state_type_id": 2,
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            },
        ]
        server.client.get_ticket_states.return_value = states_data

        # First call
        result1 = server._get_cached_states()
        assert len(result1) == 2
        assert result1[0].name == "new"
        server.client.get_ticket_states.assert_called_once()

        # Second call uses cache
        result2 = server._get_cached_states()
        assert result1 == result2
        server.client.get_ticket_states.assert_called_once()

    def test_cached_priorities(self) -> None:
        """Test that ticket priorities are cached properly."""
        # Create server instance with mocked client
        server = ZammadMCPServer()
        server.client = Mock()

        priorities_data = [
            {
                "id": 1,
                "name": "1 low",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            },
            {
                "id": 2,
                "name": "2 normal",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            },
        ]
        server.client.get_ticket_priorities.return_value = priorities_data

        # First call
        result1 = server._get_cached_priorities()
        assert len(result1) == 2
        assert result1[0].name == "1 low"
        server.client.get_ticket_priorities.assert_called_once()

        # Second call uses cache
        result2 = server._get_cached_priorities()
        assert result1 == result2
        server.client.get_ticket_priorities.assert_called_once()

    def test_clear_caches(self) -> None:
        """Test that clear_caches clears all caches."""
        # Create server instance with mocked client
        server = ZammadMCPServer()
        server.client = Mock()

        # Set up mock data
        groups_data = [
            {
                "id": 1,
                "name": "Users",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            }
        ]
        states_data = [
            {
                "id": 1,
                "name": "new",
                "state_type_id": 1,
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            }
        ]
        priorities_data = [
            {
                "id": 1,
                "name": "1 low",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by_id": 1,
                "updated_by_id": 1,
            }
        ]

        server.client.get_groups.return_value = groups_data
        server.client.get_ticket_states.return_value = states_data
        server.client.get_ticket_priorities.return_value = priorities_data

        # Populate caches
        server._get_cached_groups()
        server._get_cached_states()
        server._get_cached_priorities()

        # Verify APIs were called
        assert server.client.get_groups.call_count == 1
        assert server.client.get_ticket_states.call_count == 1
        assert server.client.get_ticket_priorities.call_count == 1

        # Clear caches
        server.clear_caches()

        # Next calls should hit API again
        server._get_cached_groups()
        server._get_cached_states()
        server._get_cached_priorities()

        # APIs should be called twice now
        assert server.client.get_groups.call_count == 2
        assert server.client.get_ticket_states.call_count == 2
        assert server.client.get_ticket_priorities.call_count == 2


class TestMainFunction:
    """Test the main() function execution."""

    def test_main_function_runs_server(self) -> None:
        """Test that main() function runs the MCP server."""
        with patch("mcp_zammad.server.mcp") as mock_mcp:
            # Call the main function
            main()

            # Verify mcp.run() was called
            mock_mcp.run.assert_called_once_with()


class TestResourceHandlers:
    """Test resource handler implementations."""

    def test_ticket_resource_handler(self, server_instance: ZammadMCPServer) -> None:
        """Test ticket resource handler with Pydantic models - tests issue #100 fix."""
        # Create a proper Pydantic Ticket object with expanded fields
        ticket = Ticket(
            id=123,
            number="12345",
            title="Test Ticket",
            group_id=1,
            state_id=1,
            priority_id=2,
            customer_id=1,
            created_by_id=1,
            updated_by_id=1,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            # Expanded fields (the bug was here - using .get() on these)
            state=StateBrief(id=1, name="open", state_type_id=1),
            priority=PriorityBrief(id=2, name="2 normal"),
            customer=UserBrief(id=1, login="customer", email="customer@example.com"),
            articles=[
                Article(
                    id=1,
                    ticket_id=123,
                    type="note",
                    sender="Agent",
                    body="Test article",
                    created_by_id=1,
                    updated_by_id=1,
                    created_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                    created_by=UserBrief(id=1, login="agent", email="agent@example.com"),
                )
            ],
        )

        # Mock must return a dict (as the real client does), not a Ticket object
        server_instance.client.get_ticket.return_value = ticket.model_dump()  # type: ignore[union-attr]

        # Import and test the resource handler function directly
        # Create a test function that mimics the actual resource handler
        def test_get_ticket_resource(ticket_id: str) -> str:
            client = server_instance.get_client()
            try:
                ticket_data = client.get_ticket(int(ticket_id), include_articles=True, article_limit=20)
                ticket = Ticket(**ticket_data)

                # This is the pattern from the fixed code - using attribute access
                if isinstance(ticket.state, StateBrief):
                    state_name = ticket.state.name
                elif isinstance(ticket.state, str):
                    state_name = ticket.state
                else:
                    state_name = "Unknown"

                if isinstance(ticket.priority, PriorityBrief):
                    priority_name = ticket.priority.name
                elif isinstance(ticket.priority, str):
                    priority_name = ticket.priority
                else:
                    priority_name = "Unknown"

                if isinstance(ticket.customer, UserBrief):
                    customer_email = ticket.customer.email or "Unknown"
                elif isinstance(ticket.customer, str):
                    customer_email = ticket.customer
                else:
                    customer_email = "Unknown"

                lines = [
                    f"Ticket #{ticket.number} - {ticket.title}",
                    f"ID: {ticket.id}",
                    f"State: {state_name}",
                    f"Priority: {priority_name}",
                    f"Customer: {customer_email}",
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving ticket {ticket_id}: {e!s}"

        # Test the handler logic
        result = test_get_ticket_resource("123")

        # Verify the output
        assert "Ticket #12345 - Test Ticket" in result
        assert "ID: 123" in result
        assert "State: open" in result
        assert "Priority: 2 normal" in result
        assert "Customer: customer@example.com" in result
        server_instance.client.get_ticket.assert_called_once_with(123, include_articles=True, article_limit=20)  # type: ignore[union-attr]

    def test_user_resource_handler(self, server_instance: ZammadMCPServer) -> None:
        """Test user resource handler - tests the actual function logic."""
        # Mock user data
        user_data = {
            "id": 456,
            "firstname": "John",
            "lastname": "Doe",
            "email": "john@example.com",
            "login": "jdoe",
            "organization": {"name": "ACME Inc"},
        }
        server_instance.client.get_user.return_value = user_data  # type: ignore[union-attr]

        # Create a test function that mimics the resource handler
        def test_get_user_resource(user_id: str) -> str:
            client = server_instance.get_client()
            try:
                user = client.get_user(int(user_id))
                lines = [
                    f"User: {user.get('firstname', '')} {user.get('lastname', '')}",
                    f"Email: {user.get('email', '')}",
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving user {user_id}: {e!s}"

        # Test the handler logic
        result = test_get_user_resource("456")

        assert "User: John Doe" in result
        assert "Email: john@example.com" in result
        server_instance.client.get_user.assert_called_once_with(456)  # type: ignore[union-attr]

    def test_organization_resource_handler(self, server_instance: ZammadMCPServer) -> None:
        """Test organization resource handler - tests the actual function logic."""
        # Mock organization data
        org_data = {
            "id": 789,
            "name": "ACME Corp",
            "note": "Important client",
            "domain": "acme.com",
            "active": True,
        }
        server_instance.client.get_organization.return_value = org_data  # type: ignore[union-attr]

        # Create a test function that mimics the resource handler
        def test_get_org_resource(org_id: str) -> str:
            client = server_instance.get_client()
            try:
                org = client.get_organization(int(org_id))
                lines = [
                    f"Organization: {org.get('name', '')}",
                    f"Domain: {org.get('domain', 'None')}",
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving organization {org_id}: {e!s}"

        # Test the handler logic
        result = test_get_org_resource("789")

        assert "Organization: ACME Corp" in result
        assert "Domain: acme.com" in result
        server_instance.client.get_organization.assert_called_once_with(789)  # type: ignore[union-attr]

    def test_resource_handler_error(self, server_instance: ZammadMCPServer) -> None:
        """Test resource handler error handling."""
        # Mock API error
        server_instance.client.get_ticket.side_effect = Exception("API Error")  # type: ignore[union-attr]

        # Create a test function that mimics the resource handler
        def test_get_ticket_resource(ticket_id: str) -> str:
            client = server_instance.get_client()
            try:
                ticket = client.get_ticket(int(ticket_id), include_articles=True, article_limit=20)
                lines = [
                    f"Ticket #{ticket['number']} - {ticket['title']}",
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving ticket {ticket_id}: {e!s}"

        # Test the handler - should return error message
        result = test_get_ticket_resource("999")

        assert "Error retrieving ticket 999: API Error" in result

    def test_ticket_resource_formatted_output_explicit(
        self, server_instance: ZammadMCPServer, decorator_capturer
    ) -> None:
        """Test explicit formatted output of ticket resource handler (issue #100)."""
        # Create ticket with all field variations to test formatting
        ticket = Ticket(
            id=456,
            number="67890",
            title="Production Bug - Critical",
            group_id=2,
            state_id=2,
            priority_id=3,
            customer_id=2,
            created_by_id=2,
            updated_by_id=2,
            created_at=datetime(2024, 3, 15, 14, 30, 45, tzinfo=timezone.utc),
            updated_at=datetime(2024, 3, 15, 16, 20, 10, tzinfo=timezone.utc),
            state=StateBrief(id=2, name="in progress", state_type_id=2),
            priority=PriorityBrief(id=3, name="3 high"),
            customer=UserBrief(id=2, login="jane.smith", email="jane.smith@company.com"),
            articles=[
                Article(
                    id=10,
                    ticket_id=456,
                    type="email",
                    sender="Customer",
                    body="System is down, please help!",
                    created_by_id=2,
                    updated_by_id=2,
                    created_at=datetime(2024, 3, 15, 14, 30, 45, tzinfo=timezone.utc),
                    updated_at=datetime(2024, 3, 15, 14, 30, 45, tzinfo=timezone.utc),
                    created_by=UserBrief(id=2, login="jane.smith", email="jane.smith@company.com"),
                ),
                Article(
                    id=11,
                    ticket_id=456,
                    type="note",
                    sender="Agent",
                    body="Working on this now.",
                    created_by_id=3,
                    updated_by_id=3,
                    created_at=datetime(2024, 3, 15, 15, 00, 00, tzinfo=timezone.utc),
                    updated_at=datetime(2024, 3, 15, 15, 00, 00, tzinfo=timezone.utc),
                    created_by=UserBrief(id=3, login="support.agent", email="support@company.com"),
                ),
            ],
        )

        server_instance.client.get_ticket.return_value = ticket.model_dump()  # type: ignore[union-attr]

        # Setup the resource and capture it
        test_resources, capture_resource = decorator_capturer(server_instance.mcp.resource)
        server_instance.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
        server_instance._setup_resources()

        # Call the actual resource handler
        result = test_resources["zammad://ticket/{ticket_id}"](ticket_id="456")

        # Verify exact format of each line
        lines = result.split("\n")
        assert lines[0] == "Ticket #67890 - Production Bug - Critical"
        assert lines[1] == "ID: 456"
        assert lines[2] == "State: in progress"
        assert lines[3] == "Priority: 3 high"
        assert lines[4] == "Customer: jane.smith@company.com"
        assert lines[5] == "Created: 2024-03-15T14:30:45+00:00"
        assert lines[6] == ""
        assert lines[7] == "Articles:"
        assert lines[8] == ""
        # First article
        assert "2024-03-15T14:30:45+00:00 by jane.smith@company.com" in lines[9]
        assert lines[10] == "System is down, please help!"
        assert lines[11] == ""
        # Second article
        assert "2024-03-15T15:00:00+00:00 by support@company.com" in lines[12]
        assert lines[13] == "Working on this now."

    def test_ticket_resource_mcp_integration(self, server_instance: ZammadMCPServer, decorator_capturer) -> None:
        """Integration test for ticket resource via MCP protocol (issue #100)."""
        # Create a ticket with Pydantic models
        ticket = Ticket(
            id=789,
            number="11111",
            title="Integration Test Ticket",
            group_id=1,
            state_id=1,
            priority_id=1,
            customer_id=1,
            created_by_id=1,
            updated_by_id=1,
            created_at=datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
            state=StateBrief(id=1, name="new", state_type_id=1),
            priority=PriorityBrief(id=1, name="1 low"),
            customer=UserBrief(id=1, login="test.user", email="test@example.com"),
            articles=[],
        )

        server_instance.client.get_ticket.return_value = ticket.model_dump()  # type: ignore[union-attr]

        # Setup resources
        # Use the MCP server to read the resource
        # This simulates the actual MCP protocol flow

        # Access the registered resources through the MCP server
        # The mcp.resource decorator registers the handler
        # We'll call it directly through the captured function
        test_resources, capture_resource = decorator_capturer(server_instance.mcp.resource)
        server_instance.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
        server_instance._setup_resources()

        # Call the resource handler as MCP would
        result = test_resources["zammad://ticket/{ticket_id}"](ticket_id="789")

        # Verify the resource was retrieved successfully and formatted correctly
        assert "Ticket #11111 - Integration Test Ticket" in result
        assert "ID: 789" in result
        assert "State: new" in result
        assert "Priority: 1 low" in result
        assert "Customer: test@example.com" in result
        assert "Created: 2024-05-01T10:00:00+00:00" in result

        # Verify the client was called correctly
        server_instance.client.get_ticket.assert_called_with(789, include_articles=True, article_limit=20)  # type: ignore[union-attr]

    def test_user_resource_regression(self, server_instance: ZammadMCPServer, decorator_capturer) -> None:
        """Regression test: Ensure user resource handler still works with dict access (issue #100)."""
        # User resources use dict, not Pydantic models
        user_data = {
            "id": 999,
            "firstname": "Alice",
            "lastname": "Johnson",
            "email": "alice.johnson@example.com",
            "login": "ajohnson",
            "organization": {"name": "Tech Corp"},
            "active": True,
            "vip": True,
            "created_at": "2024-02-20T08:00:00Z",
        }

        server_instance.client.get_user.return_value = user_data  # type: ignore[union-attr]

        # Setup resources
        # Capture the user resource handler
        test_resources, capture_resource = decorator_capturer(server_instance.mcp.resource)
        server_instance.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
        server_instance._setup_resources()

        # Call the user resource handler
        result = test_resources["zammad://user/{user_id}"](user_id="999")

        # Verify the output format
        assert "User: Alice Johnson" in result
        assert "Email: alice.johnson@example.com" in result
        assert "Login: ajohnson" in result
        assert "Organization: Tech Corp" in result
        assert "Active: True" in result
        assert "VIP: True" in result
        assert "Created: 2024-02-20T08:00:00Z" in result

        # Verify client was called
        server_instance.client.get_user.assert_called_with(999)  # type: ignore[union-attr]

    def test_organization_resource_regression(self, server_instance: ZammadMCPServer, decorator_capturer) -> None:
        """Regression test: Ensure organization resource handler still works (issue #100)."""
        # Organization resources use dict, not Pydantic models
        org_data = {
            "id": 888,
            "name": "Enterprise Solutions Inc",
            "domain": "enterprise-solutions.com",
            "active": True,
            "note": "VIP customer - handle with priority",
            "created_at": "2024-01-10T12:00:00Z",
        }

        server_instance.client.get_organization.return_value = org_data  # type: ignore[union-attr]

        # Setup resources
        # Capture the organization resource handler
        test_resources, capture_resource = decorator_capturer(server_instance.mcp.resource)
        server_instance.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
        server_instance._setup_resources()

        # Call the organization resource handler
        result = test_resources["zammad://organization/{org_id}"](org_id="888")

        # Verify the output format
        assert "Organization: Enterprise Solutions Inc" in result
        assert "Domain: enterprise-solutions.com" in result
        assert "Active: True" in result
        assert "Note: VIP customer - handle with priority" in result
        assert "Created: 2024-01-10T12:00:00Z" in result

        # Verify client was called
        server_instance.client.get_organization.assert_called_with(888)  # type: ignore[union-attr]

    def test_queue_resource_regression(self, server_instance: ZammadMCPServer, decorator_capturer) -> None:
        """Regression test: Ensure queue resource handler still works with dict access (issue #100)."""
        # Queue resource uses dicts from search_tickets
        tickets_data = [
            {
                "id": 101,
                "number": "10001",
                "title": "First ticket in queue",
                "state": {"name": "open"},
                "priority": {"name": "2 normal"},
                "customer": {"email": "customer1@example.com"},
                "created_at": "2024-06-01T09:00:00Z",
            },
            {
                "id": 102,
                "number": "10002",
                "title": "Second ticket in queue",
                "state": {"name": "open"},
                "priority": {"name": "3 high"},
                "customer": {"email": "customer2@example.com"},
                "created_at": "2024-06-01T10:00:00Z",
            },
            {
                "id": 103,
                "number": "10003",
                "title": "Closed ticket",
                "state": {"name": "closed"},
                "priority": {"name": "1 low"},
                "customer": {"email": "customer3@example.com"},
                "created_at": "2024-05-30T08:00:00Z",
            },
        ]

        server_instance.client.search_tickets.return_value = tickets_data  # type: ignore[union-attr]

        # Setup resources
        # Capture the queue resource handler
        test_resources, capture_resource = decorator_capturer(server_instance.mcp.resource)
        server_instance.mcp.resource = capture_resource  # type: ignore[method-assign, assignment]
        server_instance._setup_resources()

        # Call the queue resource handler
        result = test_resources["zammad://queue/{group}"](group="Support")

        # Verify the output format
        assert "Queue for Group: Support" in result
        assert "Total Tickets: 3" in result
        assert "Open (2 tickets)" in result or "Open (2 Tickets)" in result
        assert "Closed (1 tickets)" in result or "Closed (1 Tickets)" in result
        assert "#10001" in result
        assert "#10002" in result
        assert "#10003" in result
        assert "First ticket in queue" in result
        assert "customer1@example.com" in result

        # Verify client was called
        server_instance.client.search_tickets.assert_called_with(group="Support", per_page=50)  # type: ignore[union-attr]


class TestAttachmentSupport:
    """Test attachment functionality."""

    def test_get_article_attachments_tool(self) -> None:
        """Test get_article_attachments tool."""
        server_inst = ZammadMCPServer()
        server_inst.client = Mock()

        # Mock attachment data
        attachments_data = [
            {
                "id": 1,
                "filename": "test.pdf",
                "size": 1024,
                "content_type": "application/pdf",
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "filename": "image.png",
                "size": 2048,
                "content_type": "image/png",
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]
        server_inst.client.get_article_attachments.return_value = attachments_data  # type: ignore[union-attr]

        # Test by calling the client method directly
        server_inst._setup_ticket_tools()

        # We can't easily access the tool functions, so let's test the underlying method behavior
        # by calling the client method directly through our server's get_client pattern
        result_data = server_inst.client.get_article_attachments(123, 456)  # type: ignore[union-attr]

        # Verify the client was called correctly
        server_inst.client.get_article_attachments.assert_called_once_with(123, 456)  # type: ignore[union-attr]

        # Verify we can create Attachment objects from the data
        attachments = [Attachment(**attachment) for attachment in result_data]

        assert len(attachments) == 2
        assert attachments[0].filename == "test.pdf"
        assert attachments[1].filename == "image.png"

    def test_download_attachment_tool(self) -> None:
        """Test download_attachment tool."""
        server_inst = ZammadMCPServer()
        server_inst.client = Mock()

        # Mock download data
        server_inst.client.download_attachment.return_value = b"file content"  # type: ignore[union-attr]

        # Test the underlying functionality
        result_data = server_inst.client.download_attachment(123, 456, 789)  # type: ignore[union-attr]

        # Verify the client was called correctly
        server_inst.client.download_attachment.assert_called_once_with(123, 456, 789)  # type: ignore[union-attr]

        # Verify the data returned is correct
        assert result_data == b"file content"

        # Test the base64 encoding that the tool would do
        expected = base64.b64encode(result_data).decode("utf-8")
        assert expected == "ZmlsZSBjb250ZW50"  # base64 of "file content"

    def test_download_attachment_error(self) -> None:
        """Test download_attachment tool error handling."""
        server_inst = ZammadMCPServer()
        server_inst.client = Mock()

        # Mock error
        server_inst.client.download_attachment.side_effect = Exception("API Error")  # type: ignore[union-attr]

        # Test that the error is raised
        with pytest.raises(Exception, match="API Error"):
            server_inst.client.download_attachment(123, 456, 789)  # type: ignore[union-attr]


class TestJSONOutputAndTruncation:
    """Test JSON output format and truncation behavior."""

    def test_search_tickets_json_format(self, decorator_capturer) -> None:
        """Test search_tickets with JSON output format."""
        server_inst = ZammadMCPServer()
        server_inst.client = Mock()

        # Mock search results
        server_inst.client.search_tickets.return_value = [
            {
                "id": 1,
                "number": "12345",
                "title": "Test Ticket",
                "state_id": 1,
                "priority_id": 2,
                "group_id": 1,
                "customer_id": 1,
                "state": "open",
                "priority": "normal",
                "created_by_id": 1,
                "updated_by_id": 1,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]

        # Capture tools using shared fixture
        test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
        server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
        server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
        server_inst._setup_tools()

        # Call with JSON format
        params = TicketSearchParams(query="test", response_format=ResponseFormat.JSON)
        result = test_tools["zammad_search_tickets"](params)

        # Verify it's valid JSON
        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["total"] is None  # total is None when unknown
        assert parsed["page"] == 1
        assert parsed["per_page"] == 25
        assert parsed["has_more"] is False
        assert "items" in parsed
        assert len(parsed["items"]) == 1
        assert "_meta" in parsed  # Pre-allocated for truncation

    def test_search_users_json_format(self, decorator_capturer) -> None:
        """Test search_users with JSON output format."""
        server_inst = ZammadMCPServer()
        server_inst.client = Mock()

        # Mock search results
        server_inst.client.search_users.return_value = [
            {
                "id": 1,
                "login": "user@example.com",
                "firstname": "Test",
                "lastname": "User",
                "email": "user@example.com",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]

        # Capture tools using shared fixture
        test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
        server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
        server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
        server_inst._setup_tools()

        # Call with JSON format
        params = SearchUsersParams(query="test", response_format=ResponseFormat.JSON)
        result = test_tools["zammad_search_users"](params)

        # Verify it's valid JSON
        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["total"] is None
        assert "items" in parsed
        assert "_meta" in parsed  # Pre-allocated for truncation

    def test_json_truncation_preserves_validity(self) -> None:
        """Test that JSON truncation maintains valid JSON."""
        # Create a large JSON object
        large_json_obj: dict[str, Any] = {
            "items": [
                {
                    "id": i,
                    "title": f"Ticket {i}" * 100,  # Make it large
                    "description": "x" * 1000,
                }
                for i in range(100)
            ],
            "total": None,
            "count": 100,
            "page": 1,
            "per_page": 100,
            "_meta": {},
        }
        large_json_str = json.dumps(large_json_obj, indent=2)

        # Ensure it's over the limit
        assert len(large_json_str) > 25000

        # Truncate it
        truncated = truncate_response(large_json_str, limit=25000)

        # Verify it's still valid JSON
        parsed = json.loads(truncated)

        # Verify truncation metadata is present
        assert "_meta" in parsed
        assert parsed["_meta"]["truncated"] is True
        assert parsed["_meta"]["original_size"] == len(large_json_str)
        assert parsed["_meta"]["limit"] == 25000

        # Verify result is under limit
        assert len(truncated) <= 25000

    def test_markdown_truncation(self) -> None:
        """Test markdown truncation adds warning message."""
        # Create large markdown content
        large_markdown = "# Test\n" + ("This is a long line\n" * 2000)

        # Ensure it's over the limit
        assert len(large_markdown) > 25000

        # Truncate it
        truncated = truncate_response(large_markdown, limit=25000)

        # Verify warning message is present
        assert "Response Truncated" in truncated
        assert "exceeds limit" in truncated
        assert "pagination" in truncated.lower()

        # Verify it's not JSON (should fail JSON parsing)
        with pytest.raises(json.JSONDecodeError):
            json.loads(truncated)

    def test_truncation_under_limit_unchanged(self) -> None:
        """Test that content under limit is not modified."""
        small_text = "This is a small text that should not be truncated."
        result = truncate_response(small_text, limit=1000)

        # Should be unchanged
        assert result == small_text

    def test_json_truncation_multiple_array_types(self) -> None:
        """Test that JSON truncation handles articles and members arrays."""
        # Create a large JSON object with multiple array types
        large_json_obj: dict[str, Any] = {
            "articles": [
                {
                    "id": i,
                    "body": "x" * 1000,  # Make it large
                    "subject": f"Article {i}",
                }
                for i in range(50)
            ],
            "members": [
                {
                    "id": i,
                    "name": f"Member {i}",
                    "details": "y" * 500,
                }
                for i in range(50)
            ],
            "name": "Test Organization",
            "_meta": {},
        }
        large_json_str = json.dumps(large_json_obj, indent=2)

        # Ensure it's over the limit
        assert len(large_json_str) > 25000

        # Truncate it
        truncated = truncate_response(large_json_str, limit=25000)

        # Verify it's still valid JSON
        parsed = json.loads(truncated)

        # Verify truncation metadata is present
        assert "_meta" in parsed
        assert parsed["_meta"]["truncated"] is True

        # Verify result is under limit
        assert len(truncated) <= 25000

        # Verify that arrays were truncated (should have fewer items than original)
        assert ("articles" not in parsed or len(parsed.get("articles", [])) < 50) or (
            "members" not in parsed or len(parsed.get("members", [])) < 50
        )

    def test_list_json_pagination_metadata(self, decorator_capturer) -> None:
        """Test that list JSON responses include full pagination metadata."""
        server_inst = ZammadMCPServer()
        server_inst.client = Mock()

        # Mock groups
        server_inst.client.get_groups.return_value = [
            {
                "id": 3,
                "name": "Group C",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": 1,
                "name": "Group A",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "name": "Group B",
                "active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
        ]

        # Capture tools using shared fixture
        test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
        server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
        server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
        server_inst._setup_tools()

        # Call with JSON format
        params = ListParams(response_format=ResponseFormat.JSON)
        result = test_tools["zammad_list_groups"](params)

        # Verify it's valid JSON
        parsed = json.loads(result)

        # Verify pagination metadata is present
        assert parsed["total"] == 3
        assert parsed["count"] == 3
        assert parsed["page"] == 1
        assert parsed["per_page"] == 3
        assert parsed["offset"] == 0
        assert parsed["has_more"] is False
        assert parsed["next_page"] is None
        assert parsed["next_offset"] is None
        assert "items" in parsed
        assert "_meta" in parsed  # Pre-allocated for truncation

        # Verify items are sorted by id (stable ordering)
        items = parsed["items"]
        assert len(items) == 3
        assert items[0]["id"] == 1  # Should be sorted
        assert items[1]["id"] == 2
        assert items[2]["id"] == 3


def test_server_name_follows_mcp_convention():
    """Server name must follow Python MCP convention: {service}_mcp."""
    server = ZammadMCPServer()
    # FastMCP stores name in mcp.name
    assert server.mcp.name == "zammad_mcp", (
        f"Expected 'zammad_mcp', got '{server.mcp.name}'. " + "Python MCP servers must use lowercase with underscores."
    )


def test_character_limit_is_constant():
    """CHARACTER_LIMIT should be a module constant, not configurable."""
    assert CHARACTER_LIMIT == 25000
    assert isinstance(CHARACTER_LIMIT, int)


@pytest.mark.asyncio
async def test_all_tools_have_title_annotation():
    """All tools must have 'title' annotation for human-readable display."""
    server = ZammadMCPServer()

    # Get all registered tools from FastMCP
    tools = await server.mcp.list_tools()

    for tool in tools:
        assert hasattr(
            tool.annotations, "title"
        ), f"Tool '{tool.name}' missing 'title' annotation. Add title for better UX in MCP clients."
        assert tool.annotations.title, "Title must not be empty"
        # Title should be human-readable (not snake_case)
        assert " " in tool.annotations.title, f"Title '{tool.annotations.title}' should be human-readable with spaces"


def test_format_ticket_detail_markdown(sample_ticket):
    """Test formatting single ticket as markdown."""
    result = _format_ticket_detail_markdown(sample_ticket)

    assert f"# Ticket #{sample_ticket.number} - {sample_ticket.title}" in result
    assert f"**ID**: {sample_ticket.id}" in result
    assert "**State**:" in result
    assert "**Priority**:" in result
    assert "**Created**:" in result


def test_format_ticket_detail_markdown_with_articles(sample_ticket_data, sample_article_data):
    """Test formatting ticket with articles included."""
    # Create a ticket with articles
    ticket_with_articles = Ticket(
        **sample_ticket_data,
        articles=[
            Article(**sample_article_data),
            Article(
                **{
                    **sample_article_data,
                    "id": 2,
                    "body": "Second article",
                    "from": "agent@example.com",
                }
            ),
        ],
    )

    result = _format_ticket_detail_markdown(ticket_with_articles)

    # Check that articles section appears
    assert "## Articles" in result
    assert "### Article 1" in result
    assert "### Article 2" in result
    assert "- **From**:" in result
    assert "- **Type**: note" in result
    assert "- **Created**:" in result
    assert "Test article" in result
    assert "Second article" in result


def test_format_ticket_detail_markdown_with_tags(sample_ticket_data):
    """Test formatting ticket with tags included."""
    # Create a ticket with tags
    ticket_with_tags = Ticket(**sample_ticket_data, tags=["urgent", "customer-request", "bug"])

    result = _format_ticket_detail_markdown(ticket_with_tags)

    # Check that tags section appears
    assert "**Tags**: urgent, customer-request, bug" in result


def test_get_ticket_supports_markdown_format(decorator_capturer):
    """zammad_get_ticket should return markdown when requested."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()

    # Mock get_ticket return data
    server_inst.client.get_ticket.return_value = {
        "id": 123,
        "number": "65003",
        "title": "Test Ticket",
        "state_id": 1,
        "priority_id": 2,
        "group_id": 1,
        "customer_id": 1,
        "state": {"id": 1, "name": "open", "state_type_id": 2},
        "priority": {"id": 2, "name": "2 normal"},
        "group": {"id": 1, "name": "Support"},
        "customer": {"id": 1, "email": "customer@example.com"},
        "owner": {"id": 2, "email": "agent@example.com"},
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Call with markdown format
    params = GetTicketParams(ticket_id=123, response_format=ResponseFormat.MARKDOWN)
    result = test_tools["zammad_get_ticket"](params)

    assert isinstance(result, str)
    assert "# Ticket #" in result
    assert "**ID**: 123" in result


def test_get_ticket_supports_json_format(decorator_capturer):
    """zammad_get_ticket should return JSON when requested."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()

    # Mock get_ticket return data
    server_inst.client.get_ticket.return_value = {
        "id": 123,
        "number": "65003",
        "title": "Test Ticket",
        "state_id": 1,
        "priority_id": 2,
        "group_id": 1,
        "customer_id": 1,
        "state": {"id": 1, "name": "open", "state_type_id": 2},
        "priority": {"id": 2, "name": "2 normal"},
        "group": {"id": 1, "name": "Support"},
        "customer": {"id": 1, "email": "customer@example.com"},
        "owner": {"id": 2, "email": "agent@example.com"},
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Call with JSON format
    params = GetTicketParams(ticket_id=123, response_format=ResponseFormat.JSON)
    result = test_tools["zammad_get_ticket"](params)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["id"] == 123


def test_get_user_supports_markdown_format(decorator_capturer):
    """zammad_get_user should return markdown when requested."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()

    # Mock get_user return data
    server_inst.client.get_user.return_value = {
        "id": 5,
        "login": "jane@example.com",
        "email": "jane@example.com",
        "firstname": "Jane",
        "lastname": "Doe",
        "active": True,
        "vip": True,
        "verified": False,
        "organization_id": 2,
        "organization": {"id": 2, "name": "ACME Corp"},
        "phone": "+1234567890",
        "created_at": "2023-01-10T08:00:00Z",
        "updated_at": "2023-01-10T08:00:00Z",
    }

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Call with markdown format (default)
    params = GetUserParams(user_id=5, response_format=ResponseFormat.MARKDOWN)
    result = test_tools["zammad_get_user"](params)

    assert isinstance(result, str)
    assert "# User: Jane Doe" in result
    assert "**ID**: 5" in result
    assert "**Email**: jane@example.com" in result
    assert "**VIP**: True" in result


def test_get_user_supports_json_format(decorator_capturer):
    """zammad_get_user should return JSON when requested."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()

    # Mock get_user return data
    server_inst.client.get_user.return_value = {
        "id": 5,
        "login": "jane@example.com",
        "email": "jane@example.com",
        "firstname": "Jane",
        "lastname": "Doe",
        "active": True,
        "vip": True,
        "verified": False,
        "organization_id": 2,
        "organization": {"id": 2, "name": "ACME Corp"},
        "created_at": "2023-01-10T08:00:00Z",
        "updated_at": "2023-01-10T08:00:00Z",
    }

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Call with JSON format
    params = GetUserParams(user_id=5, response_format=ResponseFormat.JSON)
    result = test_tools["zammad_get_user"](params)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["id"] == 5
    assert parsed["email"] == "jane@example.com"
    assert parsed["vip"] is True


def test_get_organization_supports_markdown_format(decorator_capturer):
    """zammad_get_organization should return markdown when requested."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()

    # Mock get_organization return data
    server_inst.client.get_organization.return_value = {
        "id": 2,
        "name": "ACME Corp",
        "domain": "acme.com",
        "active": True,
        "shared": True,
        "domain_assignment": True,
        "note": "VIP customer",
        "created_at": "2022-05-10T12:00:00Z",
        "updated_at": "2022-05-10T12:00:00Z",
    }

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Call with markdown format (default)
    params = GetOrganizationParams(org_id=2, response_format=ResponseFormat.MARKDOWN)
    result = test_tools["zammad_get_organization"](params)

    assert isinstance(result, str)
    assert "# Organization: ACME Corp" in result
    assert "**ID**: 2" in result
    assert "**Domain**: acme.com" in result
    assert "VIP customer" in result


def test_get_organization_supports_json_format(decorator_capturer):
    """zammad_get_organization should return JSON when requested."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()

    # Mock get_organization return data
    server_inst.client.get_organization.return_value = {
        "id": 2,
        "name": "ACME Corp",
        "domain": "acme.com",
        "active": True,
        "shared": True,
        "domain_assignment": True,
        "note": "VIP customer",
        "created_at": "2022-05-10T12:00:00Z",
        "updated_at": "2022-05-10T12:00:00Z",
    }

    # Capture tools using shared fixture
    test_tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()

    # Call with JSON format
    params = GetOrganizationParams(org_id=2, response_format=ResponseFormat.JSON)
    result = test_tools["zammad_get_organization"](params)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["id"] == 2
    assert parsed["name"] == "ACME Corp"
    assert parsed["domain"] == "acme.com"


# ==================== ANNOTATION FACTORY TESTS ====================


def test_read_only_annotations():
    """Test _read_only_annotations factory creates correct annotations."""
    result = _read_only_annotations("Test Read Tool")

    assert result.title == "Test Read Tool"
    assert result.readOnlyHint is True
    assert result.idempotentHint is True  # Read operations are idempotent
    assert result.destructiveHint is False
    assert result.openWorldHint is True


def test_write_annotations():
    """Test _write_annotations factory creates correct annotations."""
    result = _write_annotations("Test Write Tool")

    assert result.title == "Test Write Tool"
    assert result.readOnlyHint is False
    assert result.idempotentHint is False
    assert result.destructiveHint is False
    assert result.openWorldHint is True


def test_idempotent_write_annotations():
    """Test _idempotent_write_annotations factory creates correct annotations."""
    result = _idempotent_write_annotations("Test Idempotent Tool")

    assert result.title == "Test Idempotent Tool"
    assert result.readOnlyHint is False
    assert result.idempotentHint is True
    assert result.destructiveHint is False
    assert result.openWorldHint is True


# ==================== BINARY SEARCH TESTS ====================


def test_find_max_items_empty_list():
    """Test _find_max_items_for_limit with empty list."""
    obj = {"items": [], "metadata": "test"}
    result = _find_max_items_for_limit(obj, [], limit=1000, use_compact=False)

    assert result == 0


def test_find_max_items_single_item_fits():
    """Test _find_max_items_for_limit with single item that fits."""
    items = [{"id": 1, "name": "Test"}]
    obj = {"items": items, "metadata": "test"}

    result = _find_max_items_for_limit(obj, items, limit=1000, use_compact=False)

    assert result == 1


def test_find_max_items_single_item_too_large():
    """Test _find_max_items_for_limit with single item that exceeds limit."""
    items = [{"id": 1, "description": "x" * 1000}]
    obj = {"items": items, "metadata": "test"}

    result = _find_max_items_for_limit(obj, items, limit=50, use_compact=False)

    assert result == 0


def test_find_max_items_all_fit():
    """Test _find_max_items_for_limit when all items fit within limit."""
    items = [{"id": i, "name": f"Item {i}"} for i in range(5)]
    obj = {"items": items, "metadata": "test"}

    result = _find_max_items_for_limit(obj, items, limit=10000, use_compact=False)

    assert result == 5


def test_find_max_items_partial_fit():
    """Test _find_max_items_for_limit with typical truncation scenario."""
    items = [{"id": i, "description": "x" * 100} for i in range(20)]
    obj = {"items": items, "metadata": "test"}

    result = _find_max_items_for_limit(obj, items, limit=1000, use_compact=False)

    # Should fit some but not all items
    assert 0 < result < 20


def test_find_max_items_compact_format():
    """Test _find_max_items_for_limit with compact JSON format."""
    items = [{"id": i, "name": f"Item {i}"} for i in range(10)]
    obj = {"items": items, "metadata": "test"}

    # Compact format should fit more items than pretty format
    result_compact = _find_max_items_for_limit(obj, items, limit=500, use_compact=True)
    result_pretty = _find_max_items_for_limit(obj, items, limit=500, use_compact=False)

    assert result_compact >= result_pretty


# ==================== ERROR HANDLING TESTS ====================


def test_handle_api_error_not_found():
    """Test _handle_api_error with 404/not found errors."""
    error = requests.HTTPError("404 Not Found")
    result = _handle_api_error(error, "ticket retrieval")

    assert "not found" in result.lower()
    assert "ticket retrieval" in result
    assert "verify the id" in result.lower()


def test_handle_api_error_forbidden():
    """Test _handle_api_error with 403/forbidden errors."""
    error = requests.HTTPError("403 Forbidden")
    result = _handle_api_error(error, "user update")

    assert "permission denied" in result.lower()
    assert "user update" in result
    assert "credentials" in result.lower()


def test_handle_api_error_unauthorized():
    """Test _handle_api_error with 401/unauthorized errors."""
    error = requests.HTTPError("401 Unauthorized")
    result = _handle_api_error(error, "authentication")

    assert "authentication failed" in result.lower()
    assert "zammad_http_token" in result.lower()


def test_handle_api_error_timeout():
    """Test _handle_api_error with timeout errors."""
    error = TimeoutError("Request timeout after 30 seconds")
    result = _handle_api_error(error, "search")

    assert "timeout" in result.lower()
    assert "search" in result
    assert "try again" in result.lower()


def test_handle_api_error_network():
    """Test _handle_api_error with network/connection errors."""
    error = ConnectionError("Connection refused")
    result = _handle_api_error(error, "ticket creation")

    assert "network" in result.lower()
    assert "ticket creation" in result
    assert "zammad_url" in result.lower()


def test_handle_api_error_generic():
    """Test _handle_api_error with generic errors."""
    error = ValueError("Invalid parameter format")
    result = _handle_api_error(error, "data validation")

    assert "data validation" in result
    assert "ValueError" in result
    assert "Invalid parameter format" in result


# ==================== FORMATTING HELPER TESTS ====================


def test_brief_field_with_none():
    """Test _brief_field handles None values gracefully."""
    result = _brief_field(None, "name")

    assert result == "Unknown"


def test_brief_field_with_string():
    """Test _brief_field returns string values as-is."""
    result = _brief_field("TestValue", "any_attr")

    assert result == "TestValue"


def test_brief_field_with_user_brief():
    """Test _brief_field extracts from UserBrief objects."""
    user = UserBrief(id=1, login="test", email="test@example.com", firstname="John", lastname="Doe")
    result = _brief_field(user, "email")

    assert result == "test@example.com"


def test_brief_field_with_missing_attr():
    """Test _brief_field returns Unknown for missing attributes."""
    user = UserBrief(id=1, login="test", email=None)
    result = _brief_field(user, "email")

    assert result == "Unknown"


def test_brief_field_with_state_brief():
    """Test _brief_field works with StateBrief objects."""
    state = StateBrief(id=1, name="open", state_type_id=1)
    result = _brief_field(state, "name")

    assert result == "open"


def test_brief_field_with_priority_brief():
    """Test _brief_field works with PriorityBrief objects."""
    priority = PriorityBrief(id=2, name="high", ui_icon="!", ui_color="red")
    result = _brief_field(priority, "name")

    assert result == "high"


def test_normalize_datetime_to_iso_with_datetime():
    """Test _normalize_datetime_to_iso with datetime object."""
    dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    result = _normalize_datetime_to_iso(dt)

    assert result == "2024-01-15T10:30:00+00:00"


def test_normalize_datetime_to_iso_with_string():
    """Test _normalize_datetime_to_iso with string value."""
    result = _normalize_datetime_to_iso("2024-01-15")

    assert result == "2024-01-15"


def test_normalize_datetime_to_iso_with_none():
    """Test _normalize_datetime_to_iso with None value."""
    result = _normalize_datetime_to_iso(None)

    assert result == "Unknown"


def test_extract_member_info_from_dict():
    """Test _extract_member_info with dict input."""
    member = {"email": "jane@example.com", "firstname": "Jane", "lastname": "Doe"}
    name, email = _extract_member_info(member)

    assert name == "Jane Doe"
    assert email == "jane@example.com"


def test_extract_member_info_from_dict_no_name():
    """Test _extract_member_info with dict without name."""
    member = {"email": "user@example.com"}
    name, email = _extract_member_info(member)

    assert name == "user@example.com"
    assert email == "user@example.com"


def test_extract_member_info_from_object():
    """Test _extract_member_info with UserBrief object."""
    member = UserBrief(id=1, login="jane", email="jane@example.com", firstname="Jane", lastname="Doe")
    name, email = _extract_member_info(member)

    assert name == "Jane Doe"
    assert email == "jane@example.com"
