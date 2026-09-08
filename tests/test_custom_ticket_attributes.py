"""Contract tests for custom Zammad ticket object attributes (issue #278)."""

import json
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from mcp_zammad.client import ZammadClient
from mcp_zammad.models import GetTicketParams, ResponseFormat, TicketSearchParams, TicketUpdateParams
from mcp_zammad.server import ZammadMCPServer

CUSTOM_ATTRIBUTES = {"region": "Lilongwe", "service_tier": "gold", "site_ids": ["LL-01", "LL-02"]}


def _ticket_payload() -> dict:
    """Build a Zammad ticket JSON payload that includes custom attributes."""
    return {
        "id": 123,
        "number": "65003",
        "title": "Fibre outage",
        "group_id": 1,
        "state_id": 1,
        "priority_id": 2,
        "customer_id": 1,
        "created_by_id": 1,
        "updated_by_id": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "state": {"id": 1, "name": "open", "state_type_id": 2},
        "priority": {"id": 2, "name": "2 normal"},
        "group": {"id": 1, "name": "Support"},
        "customer": {"id": 1, "email": "customer@example.com"},
        **CUSTOM_ATTRIBUTES,
    }


@pytest.fixture
def ticket_tools(decorator_capturer):
    """Provide captured ticket tools bound to a controlled client double."""
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()
    tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()
    return tools, server_inst.client


def test_get_ticket_json_includes_custom_attributes(ticket_tools):
    tools, client = ticket_tools
    client.get_ticket.return_value = _ticket_payload()

    result = tools["zammad_get_ticket"](GetTicketParams(ticket_id=123, response_format=ResponseFormat.JSON))

    parsed = json.loads(result)
    assert parsed["region"] == "Lilongwe"
    assert parsed["service_tier"] == "gold"
    assert parsed["site_ids"] == ["LL-01", "LL-02"]


def test_get_ticket_markdown_renders_custom_attributes(ticket_tools):
    tools, client = ticket_tools
    client.get_ticket.return_value = _ticket_payload()

    result = tools["zammad_get_ticket"](GetTicketParams(ticket_id=123, response_format=ResponseFormat.MARKDOWN))

    assert "## Custom Attributes" in result
    assert "**region**: Lilongwe" in result
    assert "**service_tier**: gold" in result
    assert "**site_ids**: LL-01, LL-02" in result


def test_get_ticket_markdown_omits_custom_section_without_custom_attributes(ticket_tools):
    tools, client = ticket_tools
    payload = _ticket_payload()
    for key in CUSTOM_ATTRIBUTES:
        del payload[key]
    client.get_ticket.return_value = payload

    result = tools["zammad_get_ticket"](GetTicketParams(ticket_id=123, response_format=ResponseFormat.MARKDOWN))

    assert "## Custom Attributes" not in result


def test_search_tickets_json_includes_custom_attributes(ticket_tools):
    tools, client = ticket_tools
    client.search_tickets.return_value = [_ticket_payload()]

    result = tools["zammad_search_tickets"](TicketSearchParams(query="outage", response_format=ResponseFormat.JSON))

    item = json.loads(result)["items"][0]
    assert item["region"] == "Lilongwe"
    assert item["service_tier"] == "gold"


def test_update_ticket_tool_forwards_custom_fields(ticket_tools):
    tools, client = ticket_tools
    client.update_ticket.return_value = _ticket_payload()

    params = TicketUpdateParams(ticket_id=123, state="open", custom_fields={"region": "Blantyre"})
    result = tools["zammad_update_ticket"](params)

    client.update_ticket.assert_called_once_with(ticket_id=123, state="open", custom_fields={"region": "Blantyre"})
    assert result.model_dump()["region"] == "Lilongwe"


@pytest.mark.parametrize("key", ["ticket_id", "title", "state", "priority", "owner", "group", "time_unit"])
def test_update_params_reject_custom_fields_colliding_with_built_in_keys(key):
    with pytest.raises(ValidationError, match=key):
        TicketUpdateParams(ticket_id=1, custom_fields={key: "value"})


def test_update_params_reject_empty_custom_field_name():
    with pytest.raises(ValidationError, match="custom_fields"):
        TicketUpdateParams(ticket_id=1, custom_fields={"": "value"})


def test_update_params_omit_custom_fields_when_not_provided():
    params = TicketUpdateParams(ticket_id=1, title="Renamed")

    assert params.model_dump(exclude={"ticket_id"}, exclude_none=True) == {"title": "Renamed"}


class TestClientCustomFields:
    """ZammadClient forwards custom attributes as top-level ticket keys."""

    @pytest.fixture
    def mock_zammad_api(self):
        with patch("mcp_zammad.client.ZammadAPI") as mock_api:
            yield mock_api

    def test_update_ticket_merges_custom_fields_into_payload(self, mock_zammad_api):
        mock_instance = Mock()
        mock_instance.ticket.update.return_value = _ticket_payload()
        mock_zammad_api.return_value = mock_instance
        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        client.update_ticket(123, priority="3 high", custom_fields={"region": "Blantyre", "service_tier": "silver"})

        mock_instance.ticket.update.assert_called_once_with(
            123, {"priority": "3 high", "region": "Blantyre", "service_tier": "silver"}
        )

    def test_update_ticket_rejects_custom_fields_overwriting_built_in_keys(self, mock_zammad_api):
        mock_instance = Mock()
        mock_zammad_api.return_value = mock_instance
        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        with pytest.raises(ValueError, match="title"):
            client.update_ticket(123, custom_fields={"title": "hijacked"})

        mock_instance.ticket.update.assert_not_called()
