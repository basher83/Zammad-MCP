"""Create-ticket custom attribute tests (issue #278 follow-up)."""

from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from mcp_zammad.client import ZammadClient
from mcp_zammad.models import TicketCreate
from mcp_zammad.server import ZammadMCPServer
from tests.test_custom_ticket_attributes import _ticket_payload


@pytest.fixture
def ticket_tools(decorator_capturer):
    """Provide captured ticket tools bound to a controlled client double.

    Args:
        decorator_capturer: Fixture that records tools registered on the server.
    """
    server_inst = ZammadMCPServer()
    server_inst.client = Mock()
    tools, capture_tool = decorator_capturer(server_inst.mcp.tool)
    server_inst.mcp.tool = capture_tool  # type: ignore[method-assign, assignment]
    server_inst.get_client = lambda: server_inst.client  # type: ignore[method-assign, assignment, return-value]
    server_inst._setup_tools()
    return tools, server_inst.client


def test_create_ticket_tool_forwards_custom_fields(ticket_tools):
    """Forward custom_fields from zammad_create_ticket to the client.

    Args:
        ticket_tools: Captured tools and the client double they call.
    """
    tools, client = ticket_tools
    client.create_ticket.return_value = _ticket_payload()

    params = TicketCreate(
        title="Fibre outage",
        group="Support",
        customer="customer@example.com",
        article_body="Down since 09:00",
        custom_fields={"category": "Incident"},
    )
    tools["zammad_create_ticket"](**params.model_dump())

    assert client.create_ticket.call_args.kwargs["custom_fields"] == {"category": "Incident"}


def test_create_params_omit_custom_fields_when_not_provided():
    """Omit custom_fields from the payload when the caller did not set it."""
    params = TicketCreate(title="t", group="Support", customer="c@example.com", article_body="b")

    assert "custom_fields" not in params.model_dump(exclude_none=True)


@pytest.mark.parametrize(
    "key",
    ["title", "group", "customer", "state", "priority", "article", "article_body", "customer_id", "group_id"],
)
def test_create_params_reject_custom_fields_colliding_with_built_in_keys(key):
    """Reject a custom field name that would override a built-in create field.

    Args:
        key: Reserved field name that must not appear in custom_fields.
    """
    with pytest.raises(ValidationError, match=key):
        TicketCreate(title="t", group="g", customer="c", article_body="b", custom_fields={key: "value"})


def test_create_params_reject_empty_custom_field_name():
    """Reject an empty custom field name."""
    with pytest.raises(ValidationError, match="custom_fields"):
        TicketCreate(title="t", group="g", customer="c", article_body="b", custom_fields={"": "value"})


class TestClientCreateCustomFields:
    """ZammadClient merges custom attributes into the create payload."""

    @pytest.fixture
    def mock_zammad_api(self):
        """Patch the Zammad API constructor.

        Returns:
            The patched constructor.
        """
        with patch("mcp_zammad.client.ZammadAPI") as mock_api:
            yield mock_api

    def test_create_ticket_merges_custom_fields_into_payload(self, mock_zammad_api):
        """Send custom attributes as top-level keys beside the built-in fields.

        Args:
            mock_zammad_api: Patched Zammad API constructor.
        """
        mock_instance = Mock()
        mock_instance.ticket.create.return_value = _ticket_payload()
        mock_zammad_api.return_value = mock_instance
        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        client.create_ticket(
            title="Fibre outage",
            group="Support",
            customer="customer@example.com",
            article_body="Down",
            custom_fields={"category": "Incident", "region": "Blantyre"},
        )

        payload = mock_instance.ticket.create.call_args.args[0]
        assert payload["category"] == "Incident"
        assert payload["region"] == "Blantyre"
        assert payload["article"]["body"] == "Down"
        assert payload["title"] == "Fibre outage"

    def test_create_ticket_rejects_custom_fields_overwriting_built_in_keys(self, mock_zammad_api):
        """Refuse a custom field that would replace the article payload.

        Args:
            mock_zammad_api: Patched Zammad API constructor.
        """
        mock_instance = Mock()
        mock_zammad_api.return_value = mock_instance
        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        with pytest.raises(ValueError, match="article"):
            client.create_ticket(
                title="t", group="g", customer="c", article_body="b", custom_fields={"article": {"body": "x"}}
            )

        mock_instance.ticket.create.assert_not_called()

    def test_create_ticket_rejects_association_id_alias(self, mock_zammad_api):
        """Refuse customer_id so it cannot override the customer argument.

        Args:
            mock_zammad_api: Patched Zammad API constructor.
        """
        mock_instance = Mock()
        mock_zammad_api.return_value = mock_instance
        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")

        with pytest.raises(ValueError, match="customer_id"):
            client.create_ticket(
                title="t", group="g", customer="c", article_body="b", custom_fields={"customer_id": 42}
            )

        mock_instance.ticket.create.assert_not_called()
