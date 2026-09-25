"""Tests for the zammad_merge_tickets MCP tool."""

from unittest.mock import Mock

import pytest

from mcp_zammad.models import TicketMergeParams, TicketMergeResult
from mcp_zammad.server import ZammadMCPServer

TARGET_TICKET = {
    "id": 20,
    "number": "20002",
    "title": "Incident: cron failures",
    "group_id": 1,
    "state_id": 2,
    "priority_id": 2,
    "customer_id": 3,
    "created_by_id": 1,
    "updated_by_id": 1,
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-09-01T00:00:00Z",
}


@pytest.fixture
def merge_tool(decorator_capturer):
    """Build a server with a mocked client and return (client, tool callable)."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()
    tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool
    server_inst.get_client = lambda: server_inst.client
    server_inst._setup_tools()
    return server_inst.client, tools["zammad_merge_tickets"]


def test_merge_tool_returns_target_ticket(merge_tool) -> None:
    client, tool = merge_tool
    client.merge_tickets.return_value = {"result": "success", "target_ticket": TARGET_TICKET}

    result = tool(TicketMergeParams(source_ticket_id=10, target_ticket_number="20002"))

    assert isinstance(result, TicketMergeResult)
    assert result.result == "success"
    assert result.target_ticket.id == 20
    client.merge_tickets.assert_called_once_with(
        source_ticket_id=10, target_ticket_number="20002", target_ticket_id=None
    )


def test_merge_tool_passes_target_id(merge_tool) -> None:
    client, tool = merge_tool
    client.merge_tickets.return_value = {"result": "success", "target_ticket": TARGET_TICKET}

    tool(TicketMergeParams(source_ticket_id=10, target_ticket_id=20))

    client.merge_tickets.assert_called_once_with(source_ticket_id=10, target_ticket_number=None, target_ticket_id=20)


def test_merge_tool_surfaces_client_failure(merge_tool) -> None:
    client, tool = merge_tool
    client.merge_tickets.side_effect = ValueError("Zammad refused to merge")

    with pytest.raises(ValueError, match="refused to merge"):
        tool(TicketMergeParams(source_ticket_id=10, target_ticket_number="20002"))


@pytest.mark.asyncio
async def test_merge_tool_is_annotated_destructive() -> None:
    tools = await ZammadMCPServer().mcp.list_tools()
    merge = next(tool for tool in tools if tool.name == "zammad_merge_tickets")

    assert merge.annotations.title == "Merge Tickets"
    assert merge.annotations.destructiveHint is True
    assert merge.annotations.readOnlyHint is False
    assert merge.annotations.idempotentHint is False
