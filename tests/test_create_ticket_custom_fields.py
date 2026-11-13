"""Create-ticket custom attribute tests (issue #278 follow-up)."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client
from pydantic import ValidationError

from mcp_zammad.client import ZammadClient
from mcp_zammad.models import TicketCreate
from mcp_zammad.server import ZammadMCPServer
from tests.test_custom_ticket_attributes import _ticket_payload


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run each test with no Zammad configuration, no dotenv files, and a throwaway cwd.

    Args:
        tmp_path: Empty directory used as the working directory.
        monkeypatch: Fixture that changes the working directory and environment.

    Yields:
        Control to the test; os.environ is restored afterwards.
    """
    for name in [name for name in os.environ if name.startswith("ZAMMAD_")]:
        monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ), patch("mcp_zammad.server.load_dotenv"):
        yield


@pytest.fixture
def server_with_client_double() -> Iterator[tuple[ZammadMCPServer, Mock]]:
    """Provide an MCP server wired to a controlled Zammad client double.

    Yields:
        The server and the client double its tools call.
    """
    zammad = Mock()
    zammad.get_current_user.return_value = {"id": 1, "email": "agent@example.com"}
    zammad.create_ticket.return_value = _ticket_payload()
    with patch("mcp_zammad.server.ZammadClient", return_value=zammad):
        yield ZammadMCPServer(), zammad


@pytest.mark.asyncio
async def test_create_ticket_tool_forwards_custom_fields(
    server_with_client_double: tuple[ZammadMCPServer, Mock],
) -> None:
    """Forward custom_fields from the zammad_create_ticket tool call to the client.

    Args:
        server_with_client_double: Server and the client double its tools call.
    """
    server, zammad = server_with_client_double
    arguments: dict[str, Any] = {
        "title": "Fibre outage",
        "group": "Support",
        "customer": "customer@example.com",
        "article_body": "Down since 09:00",
        "custom_fields": {"category": "Incident"},
    }

    async with Client(server.mcp) as client:
        await client.call_tool("zammad_create_ticket", arguments)

    assert zammad.create_ticket.call_args.kwargs["custom_fields"] == {"category": "Incident"}


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
