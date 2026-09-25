"""Tests for the zammad_bulk_update_tickets MCP tool."""

from typing import Any
from unittest.mock import Mock, call, patch

import pytest

from mcp_zammad.models import BulkTicketUpdateParams
from mcp_zammad.server import ZammadMCPServer


@pytest.fixture
def bulk_server() -> ZammadMCPServer:
    """Server wired to a controlled client double (no Zammad access)."""
    server = ZammadMCPServer()
    server.client = Mock()
    return server


async def _run_bulk(server: ZammadMCPServer, **kwargs: Any) -> Any:
    tool = await server.mcp.get_tool("zammad_bulk_update_tickets")
    return tool.fn(BulkTicketUpdateParams(**kwargs))


@pytest.mark.asyncio
async def test_tool_is_registered_as_destructive(bulk_server):
    """The bulk tool is exposed and flagged as destructive."""
    tool = await bulk_server.mcp.get_tool("zammad_bulk_update_tickets")
    assert tool.annotations is not None
    assert tool.annotations.destructiveHint is True
    assert tool.annotations.readOnlyHint is False


@pytest.mark.asyncio
async def test_updates_every_ticket_with_requested_fields(bulk_server):
    """Ticket fields are forwarded to each ticket via the client boundary."""
    result = await _run_bulk(bulk_server, ticket_ids=[1, 2], state="closed", owner="agent@example.com")

    assert bulk_server.client.update_ticket.call_args_list == [
        call(ticket_id=1, state="closed", owner="agent@example.com"),
        call(ticket_id=2, state="closed", owner="agent@example.com"),
    ]
    assert result.successful_ticket_ids == [1, 2]
    assert result.failed == []
    assert result.total_processed == 2
    assert result.total_successful == 2


@pytest.mark.asyncio
async def test_applies_tags_and_note_without_field_update(bulk_server):
    """Tag and note actions work on their own and never call update_ticket."""
    result = await _run_bulk(
        bulk_server, ticket_ids=[7], add_tags=["vip", "urgent"], remove_tags=["stale"], note="Bulk note"
    )

    bulk_server.client.update_ticket.assert_not_called()
    assert bulk_server.client.add_ticket_tag.call_args_list == [call(7, "vip"), call(7, "urgent")]
    bulk_server.client.remove_ticket_tag.assert_called_once_with(7, "stale")
    bulk_server.client.add_article.assert_called_once_with(
        ticket_id=7, body="Bulk note", article_type="note", internal=True
    )
    assert result.successful_ticket_ids == [7]


@pytest.mark.asyncio
async def test_continues_after_failure_and_reports_reason(bulk_server):
    """One failing ticket does not stop the batch, and its reason is reported."""
    bulk_server.client.update_ticket.side_effect = [
        {"id": 1},
        Exception("Ticket not found"),
        {"id": 3},
    ]

    result = await _run_bulk(bulk_server, ticket_ids=[1, 2, 3], priority="3 high")

    assert bulk_server.client.update_ticket.call_count == 3
    assert result.successful_ticket_ids == [1, 3]
    assert [f.ticket_id for f in result.failed] == [2]
    assert "Resource not found" in result.failed[0].error
    assert result.total_processed == 3
    assert result.total_successful == 2


@pytest.mark.asyncio
async def test_ticket_fails_when_tag_step_fails(bulk_server):
    """A ticket is only successful when every requested action succeeds."""
    bulk_server.client.add_ticket_tag.side_effect = Exception("forbidden")

    result = await _run_bulk(bulk_server, ticket_ids=[5], state="open", add_tags=["vip"])

    bulk_server.client.update_ticket.assert_called_once_with(ticket_id=5, state="open")
    assert result.successful_ticket_ids == []
    assert result.failed[0].ticket_id == 5
    assert "Permission denied" in result.failed[0].error


@pytest.mark.asyncio
async def test_delay_applies_only_between_tickets(bulk_server):
    """delay_seconds sleeps between tickets, not after the last one."""
    with patch("mcp_zammad.server.time.sleep") as sleep:
        await _run_bulk(bulk_server, ticket_ids=[1, 2, 3], state="closed", delay_seconds=0.25)

    assert sleep.call_args_list == [call(0.25), call(0.25)]


@pytest.mark.asyncio
async def test_no_sleep_without_delay(bulk_server):
    """No throttling happens by default."""
    with patch("mcp_zammad.server.time.sleep") as sleep:
        await _run_bulk(bulk_server, ticket_ids=[1, 2], state="closed")

    sleep.assert_not_called()
