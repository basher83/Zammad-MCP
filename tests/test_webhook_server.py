"""Server-level tests: HTTP webhook route and the zammad_list_events MCP tool."""

import hashlib
import hmac
import json
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client

from mcp_zammad.events import EventStore, WebhookEvent
from mcp_zammad.server import ZammadMCPServer

SECRET = "server-test-secret"
ROUTE = "/webhooks/zammad"


def signed(payload: dict, secret: str = SECRET) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode()
    signature = "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    return body, {"content-type": "application/json", "x-hub-signature": signature}


@pytest.fixture
def zammad_client() -> Iterator[Mock]:
    """Stand-in for the Zammad API so lifespan startup never touches the network."""
    with patch("mcp_zammad.server.ZammadClient") as client_cls:
        instance = Mock()
        instance.get_current_user.return_value = {"id": 1}
        client_cls.return_value = instance
        yield instance


@pytest.fixture
def server_with_secret(zammad_client: Mock) -> Iterator[ZammadMCPServer]:
    with patch.dict("os.environ", {"ZAMMAD_WEBHOOK_SECRET": SECRET}):
        yield ZammadMCPServer(event_store=EventStore(capacity=3))


@pytest_asyncio.fixture
async def http(server_with_secret: ZammadMCPServer) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=server_with_secret.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_signed_delivery_is_accepted_over_http(http: httpx.AsyncClient) -> None:
    body, headers = signed({"ticket": {"id": 7, "number": "10007"}})

    response = await http.post(ROUTE, content=body, headers=headers)

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "event_type": "ticket.update", "ticket_id": 7}


@pytest.mark.asyncio
async def test_bad_signature_is_rejected_over_http(http: httpx.AsyncClient) -> None:
    body, headers = signed({"ticket": {"id": 7}}, secret="wrong")

    response = await http.post(ROUTE, content=body, headers=headers)

    assert response.status_code == 401
    assert response.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_unset_secret_returns_503_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZAMMAD_WEBHOOK_SECRET", raising=False)
    server = ZammadMCPServer(event_store=EventStore(capacity=3))
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    body, headers = signed({"ticket": {"id": 7}})

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        response = await http.post(ROUTE, content=body, headers=headers)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_list_events_tool_is_registered_read_only(server_with_secret: ZammadMCPServer) -> None:
    async with Client(server_with_secret.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    tool = tools["zammad_list_events"]
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False


@pytest.mark.asyncio
async def test_accepted_delivery_is_observable_via_tool_without_zammad_calls(
    server_with_secret: ZammadMCPServer, http: httpx.AsyncClient, zammad_client: Mock
) -> None:
    body, headers = signed({"ticket": {"id": 7, "number": "10007", "article_count": 2}, "article": {"id": 44}})
    await http.post(ROUTE, content=body, headers=headers)

    async with Client(server_with_secret.mcp) as client:
        zammad_client.reset_mock()
        result = await client.call_tool("zammad_list_events", {"params": {"limit": 10}})

    assert zammad_client.method_calls == []
    data = result.structured_content
    assert data["count"] == 1
    assert data["capacity"] == 3
    assert data["retained_total"] == 1
    [event] = data["events"]
    assert event["event_type"] == "ticket.article.create"
    assert event["ticket_id"] == 7
    assert event["article_id"] == 44
    assert data["next_since"] == event["received_at"]


@pytest.mark.asyncio
async def test_list_events_tool_filters_since_and_limit(server_with_secret: ZammadMCPServer) -> None:
    store = server_with_secret.event_store
    base = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    for seq in range(1, 4):
        store.append(WebhookEvent(event_type="ticket.update", ticket_id=seq, received_at=base.replace(minute=seq)))

    async with Client(server_with_secret.mcp) as client:
        result = await client.call_tool("zammad_list_events", {"params": {"since": "2026-09-08T12:01:00Z", "limit": 1}})

    data = result.structured_content
    assert [e["ticket_id"] for e in data["events"]] == [3]
    assert data["retained_total"] == 3
    assert data["next_since"].startswith("2026-09-08T12:03:00")


@pytest.mark.asyncio
async def test_list_events_tool_rejects_invalid_limit(server_with_secret: ZammadMCPServer) -> None:
    async with Client(server_with_secret.mcp) as client:
        result = await client.call_tool("zammad_list_events", {"params": {"limit": 0}}, raise_on_error=False)

    assert result.is_error


@pytest.mark.asyncio
async def test_empty_store_returns_null_cursor(server_with_secret: ZammadMCPServer) -> None:
    async with Client(server_with_secret.mcp) as client:
        result = await client.call_tool("zammad_list_events", {"params": {}})

    assert result.structured_content == {
        "events": [],
        "count": 0,
        "capacity": 3,
        "retained_total": 0,
        "next_since": None,
    }
