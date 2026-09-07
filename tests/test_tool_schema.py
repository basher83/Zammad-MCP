"""Boundary tests for flat tool argument schemas (issue #212).

AI agents send tool arguments as a flat dict. Every tool must expose its
parameters at the top level of ``inputSchema`` and accept flat calls, while
still enforcing the Pydantic validation rules defined in ``mcp_zammad.models``.
"""

from collections.abc import Iterator
from typing import Any, NamedTuple
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_zammad.server import ZammadMCPServer

TICKET_DATA: dict[str, Any] = {
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

ARTICLE_DATA: dict[str, Any] = {
    "id": 1,
    "ticket_id": 1,
    "body": "Test article",
    "type": "email",
    "sender": "Agent",
    "created_by_id": 1,
    "updated_by_id": 1,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
}


class Harness(NamedTuple):
    """An MCP server wired to a controlled Zammad client double."""

    server: ZammadMCPServer
    zammad: Mock


@pytest.fixture
def harness() -> Iterator[Harness]:
    zammad = Mock()
    zammad.get_current_user.return_value = {"id": 1, "email": "agent@example.com"}
    zammad.get_ticket.return_value = TICKET_DATA
    zammad.add_article.return_value = ARTICLE_DATA
    with patch("mcp_zammad.server.ZammadClient", return_value=zammad):
        yield Harness(ZammadMCPServer(), zammad)


async def _tool_schemas(server: ZammadMCPServer) -> dict[str, dict[str, Any]]:
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
    return {tool.name: tool.inputSchema for tool in tools}


async def _call_expecting_error(server: ZammadMCPServer, name: str, arguments: dict[str, Any]) -> str:
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(name, arguments)
    return str(exc_info.value)


@pytest.mark.asyncio
async def test_no_tool_wraps_arguments_in_params(harness: Harness) -> None:
    schemas = await _tool_schemas(harness.server)
    wrapped = [name for name, schema in schemas.items() if list(schema.get("properties", {})) == ["params"]]
    assert wrapped == [], f"Tools still wrap arguments in a single 'params' object: {wrapped}"


@pytest.mark.asyncio
async def test_get_ticket_schema_is_flat(harness: Harness) -> None:
    schemas = await _tool_schemas(harness.server)
    schema = schemas["zammad_get_ticket"]
    assert set(schema["properties"]) >= {"ticket_id", "include_articles", "article_limit", "article_offset"}
    assert schema.get("required") == ["ticket_id"]


@pytest.mark.asyncio
async def test_get_ticket_accepts_flat_arguments(harness: Harness) -> None:
    async with Client(harness.server.mcp) as client:
        result = await client.call_tool("zammad_get_ticket", {"ticket_id": 1, "include_articles": False})
    assert "Test Ticket" in result.content[0].text
    harness.zammad.get_ticket.assert_called_once_with(
        ticket_id=1, include_articles=False, article_limit=10, article_offset=0
    )


@pytest.mark.asyncio
async def test_flat_arguments_still_enforce_field_constraints(harness: Harness) -> None:
    message = await _call_expecting_error(harness.server, "zammad_get_ticket", {"ticket_id": -1})
    assert "greater than 0" in message
    harness.zammad.get_ticket.assert_not_called()


@pytest.mark.asyncio
async def test_flat_arguments_reject_unknown_fields(harness: Harness) -> None:
    message = await _call_expecting_error(harness.server, "zammad_get_ticket", {"ticket_id": 1, "bogus": True})
    assert "bogus" in message
    assert "params" not in message
    harness.zammad.get_ticket.assert_not_called()


@pytest.mark.asyncio
async def test_add_article_exposes_field_name_and_sanitizes_body(harness: Harness) -> None:
    schemas = await _tool_schemas(harness.server)
    properties = schemas["zammad_add_article"]["properties"]
    assert "article_type" in properties
    assert "type" not in properties

    async with Client(harness.server.mcp) as client:
        await client.call_tool("zammad_add_article", {"ticket_id": 1, "body": "<b>hi</b>", "article_type": "email"})
    call_kwargs = harness.zammad.add_article.call_args.kwargs
    assert call_kwargs["article_type"] == "email"
    assert call_kwargs["body"] == "&lt;b&gt;hi&lt;/b&gt;"
