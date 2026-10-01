"""
Boundary tests for client-visible text of resources and prompts.

Agents read resource bodies and prompt text as contracts. These tests check,
through the public FastMCP boundary, that the text claims only what the server
can actually deliver.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client

from mcp_zammad.server import ZammadMCPServer

QUEUE_PAGE_SIZE = 50
ESCALATION_FIELDS = ("first_response_escalation_at", "update_escalation_at", "close_escalation_at")


def _ticket(ticket_id: int) -> dict[str, Any]:
    return {
        "id": ticket_id,
        "number": f"{10000 + ticket_id}",
        "title": f"Issue {ticket_id}",
        "state": "open",
        "priority": "2 normal",
        "customer": "customer@example.com",
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def zammad() -> Iterator[Mock]:
    double = Mock()
    with patch("mcp_zammad.server.ZammadClient", return_value=double):
        yield double


@pytest.fixture
def server(zammad: Mock) -> ZammadMCPServer:
    return ZammadMCPServer()


async def _read_queue(server: ZammadMCPServer, group: str) -> str:
    async with Client(server.mcp) as client:
        contents = await client.read_resource(f"zammad://queue/{group}")
    return contents[0].text  # type: ignore[union-attr]


async def _escalation_prompt(server: ZammadMCPServer) -> str:
    async with Client(server.mcp) as client:
        result = await client.get_prompt("escalation_summary", {"group": "Support"})
    return result.messages[0].content.text  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_queue_resource_does_not_claim_a_total_for_a_full_page(server: ZammadMCPServer, zammad: Mock) -> None:
    zammad.search_tickets.return_value = [_ticket(i) for i in range(1, QUEUE_PAGE_SIZE + 1)]
    text = await _read_queue(server, "Support")
    assert "Total Tickets" not in text
    assert f"Tickets fetched: {QUEUE_PAGE_SIZE} (first {QUEUE_PAGE_SIZE})" in text


@pytest.mark.asyncio
async def test_queue_resource_labels_a_partial_page_as_fetched_count(server: ZammadMCPServer, zammad: Mock) -> None:
    zammad.search_tickets.return_value = [_ticket(1), _ticket(2)]
    text = await _read_queue(server, "Support")
    assert "Total Tickets" not in text
    assert "Tickets fetched: 2" in text
    assert "(first" not in text


@pytest.mark.asyncio
async def test_escalation_prompt_names_real_fields_not_a_missing_filter(server: ZammadMCPServer) -> None:
    text = await _escalation_prompt(server)
    assert "escalation times set" not in text
    assert "zammad_search_tickets" in text
    assert "group" in text and "state" in text
    for field in ESCALATION_FIELDS:
        assert field in text


@pytest.mark.asyncio
async def test_queue_resource_does_not_call_the_page_count_shown_when_states_are_capped(
    server: ZammadMCPServer, zammad: Mock
) -> None:
    zammad.search_tickets.return_value = [_ticket(i) for i in range(1, QUEUE_PAGE_SIZE + 1)]
    text = await _read_queue(server, "Support")
    assert "Tickets shown" not in text
    assert "more tickets" in text


@pytest.mark.asyncio
async def test_escalation_prompt_checks_truncation_before_following_next_page(server: ZammadMCPServer) -> None:
    text = await _escalation_prompt(server)
    assert "_meta.truncated" in text
    assert "per_page" in text
    assert text.index("_meta.truncated") < text.index("next_page")
