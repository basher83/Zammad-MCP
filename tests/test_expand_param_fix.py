"""Tests proving the expand parameter bug and fix.

Bug: The Zammad API is case-sensitive for the `expand` query parameter.
Python's `requests` library serializes bool `True` as the string "True"
(capital T), but Zammad only recognizes lowercase "true". When "True" is
sent, the API returns a nested dict format instead of a flat list, causing
`Ticket(**item)` to fail with "argument after ** must be a mapping, not str".

Fix: Use the string "true" instead of Python bool `True` for the expand
parameter in all filter dicts passed to zammad_py.
"""

from unittest.mock import Mock, patch

import pytest

from mcp_zammad.client import ZammadClient
from mcp_zammad.models import Ticket

# -- Sample data matching real Zammad API responses --

# What Zammad returns when expand=true (lowercase) — a flat list of dicts
EXPANDED_TICKET_LIST = [
    {
        "id": 157656,
        "number": "202602261700956",
        "title": "Test Ticket 1",
        "group_id": 8,
        "group": "Support",
        "state_id": 2,
        "state": "open",
        "priority_id": 2,
        "priority": "2 normal",
        "customer_id": 4541,
        "owner_id": 6009,
        "organization_id": 22,
        "created_by_id": 6009,
        "updated_by_id": 4541,
        "created_at": "2026-02-26T21:36:59.832Z",
        "updated_at": "2026-03-03T21:46:36.412Z",
    },
]

# What Zammad returns when expand=True (capital T) or expand missing — nested dict
UNEXPANDED_TICKET_DICT = {
    "tickets": [157656],
    "tickets_count": 1,
    "assets": {
        "Ticket": {
            "157656": {
                "id": 157656,
                "number": "202602261700956",
                "title": "Test Ticket 1",
                "group_id": 8,
                "state_id": 2,
                "priority_id": 2,
                "customer_id": 4541,
                "owner_id": 6009,
                "organization_id": 22,
                "created_by_id": 6009,
                "updated_by_id": 4541,
                "created_at": "2026-02-26T21:36:59.832Z",
                "updated_at": "2026-03-03T21:46:36.412Z",
            }
        }
    },
}


class TestExpandParameterBug:
    """Tests demonstrating the expand parameter bug and its fix."""

    @pytest.fixture
    def mock_zammad_api(self):
        with patch("mcp_zammad.client.ZammadAPI") as mock_api:
            yield mock_api

    def test_expand_param_is_string_not_bool(self, mock_zammad_api: Mock) -> None:
        """Verify the fix: expand parameter must be string "true", not bool True.

        zammad_py checks `if "expand" not in params` before setting its own
        default. When we pass bool True, zammad_py skips its override and
        Python's requests serializes True -> "True" (capital T). Zammad
        ignores this and returns the nested dict format.
        """
        mock_instance = Mock()
        mock_instance.ticket.search.return_value = EXPANDED_TICKET_LIST
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")
        client.search_tickets(state="open")

        call_args = mock_instance.ticket.search.call_args
        filters = call_args[1]["filters"]

        # The fix: expand must be the string "true", not Python bool True
        assert filters["expand"] == "true"
        assert isinstance(filters["expand"], str), (
            "expand must be a string, not bool. "
            "Python bool True serializes to 'True' (capital T) which Zammad ignores."
        )

    def test_expand_param_string_in_search_users(self, mock_zammad_api: Mock) -> None:
        """Verify expand is string "true" for user search."""
        mock_instance = Mock()
        mock_instance.user.search.return_value = []
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")
        client.search_users("test")

        filters = mock_instance.user.search.call_args[1]["filters"]
        assert filters["expand"] == "true"
        assert isinstance(filters["expand"], str)

    def test_expand_param_string_in_search_organizations(self, mock_zammad_api: Mock) -> None:
        """Verify expand is string "true" for organization search."""
        mock_instance = Mock()
        mock_instance.organization.search.return_value = []
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")
        client.search_organizations("test")

        filters = mock_instance.organization.search.call_args[1]["filters"]
        assert filters["expand"] == "true"
        assert isinstance(filters["expand"], str)

    def test_expand_param_string_in_ticket_all(self, mock_zammad_api: Mock) -> None:
        """Verify expand is string "true" when listing all tickets (no query)."""
        mock_instance = Mock()
        mock_instance.ticket.all.return_value = EXPANDED_TICKET_LIST
        mock_zammad_api.return_value = mock_instance

        client = ZammadClient(url="https://test.zammad.com/api/v1", http_token="test-token")
        client.search_tickets()  # no query -> falls through to ticket.all()

        filters = mock_instance.ticket.all.call_args[1]["filters"]
        assert filters["expand"] == "true"
        assert isinstance(filters["expand"], str)


class TestUnexpandedResponseFailure:
    """Tests proving that the unexpanded (nested dict) response causes failures."""

    def test_iterating_unexpanded_dict_yields_strings(self) -> None:
        """Demonstrate the root cause: iterating a dict yields key strings.

        When Zammad returns the nested format (expand not recognized),
        list(response) produces dict keys like ["tickets", "tickets_count", "assets"].
        The code then tries Ticket(**"tickets") which fails.
        """
        # Simulating what happens when zammad_py wraps the unexpanded response
        items = list(UNEXPANDED_TICKET_DICT)

        assert items == ["tickets", "tickets_count", "assets"]
        assert all(isinstance(item, str) for item in items)

        # This is exactly what fails in server.py line 940:
        #   tickets = [Ticket(**ticket) for ticket in tickets_data]
        with pytest.raises(TypeError, match="must be a mapping, not str"):
            Ticket(**items[0])

    def test_iterating_expanded_list_yields_dicts(self) -> None:
        """Demonstrate the fix: expanded response yields ticket dicts.

        When Zammad correctly receives expand=true (lowercase), it returns
        a flat list of ticket dicts that can be unpacked into Ticket models.
        """
        items = list(EXPANDED_TICKET_LIST)

        assert len(items) == 1
        assert isinstance(items[0], dict)

        # This works correctly
        ticket = Ticket(**items[0])
        assert ticket.id == 157656
        assert ticket.title == "Test Ticket 1"


class TestBoolVsStringSerialization:
    """Tests showing how Python requests serializes bool vs string."""

    def test_bool_true_serializes_to_capital_t(self) -> None:
        """Python bool True becomes 'True' (capital T) in query strings.

        The `requests` library calls str() on parameter values, and
        str(True) == 'True'. Zammad requires lowercase 'true'.
        """
        assert str(True) == "True"
        assert str(True) != "true"

    def test_string_true_stays_lowercase(self) -> None:
        """String "true" stays as-is in query strings."""
        assert str("true") == "true"
