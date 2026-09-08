"""Tests for ZammadClient.merge_tickets against a controlled HTTP session."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
import requests

from mcp_zammad.client import ZammadClient

URL = "https://test.zammad.com/api/v1"
MERGE_URL = f"{URL}/ticket_merge/10/20002"
TARGET = {"id": 20, "number": "20002", "title": "Incident"}


@pytest.fixture
def api() -> Generator[Mock, None, None]:
    """Mock zammad_py.ZammadAPI and return the instance the client will use."""
    with patch("mcp_zammad.client.ZammadAPI") as mock_api:
        instance = Mock()
        mock_api.return_value = instance
        yield instance


def _put_response(payload: dict, status_error: Exception | None = None) -> Mock:
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status = Mock(side_effect=status_error)
    return response


def test_merge_by_target_number(api: Mock) -> None:
    api.session.put.return_value = _put_response({"result": "success", "target_ticket": TARGET})
    client = ZammadClient(url=URL, http_token="test-token")

    result = client.merge_tickets(10, target_ticket_number="20002")

    assert result["result"] == "success"
    assert result["target_ticket"]["id"] == 20
    api.session.put.assert_called_once_with(MERGE_URL)
    api.ticket.find.assert_not_called()


@pytest.mark.parametrize(
    ("number", "encoded"),
    [
        ("../../tickets/7", "..%2F..%2Ftickets%2F7"),
        ("abc?x=1", "abc%3Fx%3D1"),
        ("20002", "20002"),
    ],
)
def test_merge_encodes_target_number_as_single_path_segment(api: Mock, number: str, encoded: str) -> None:
    """A caller-supplied number must never redirect the authenticated PUT to another endpoint."""
    api.session.put.return_value = _put_response({"result": "success", "target_ticket": TARGET})
    client = ZammadClient(url=URL, http_token="test-token")

    client.merge_tickets(10, target_ticket_number=number)

    api.session.put.assert_called_once_with(f"{URL}/ticket_merge/10/{encoded}")


def test_merge_by_target_id_resolves_number(api: Mock) -> None:
    api.ticket.find.return_value = dict(TARGET)
    api.session.put.return_value = _put_response({"result": "success", "target_ticket": TARGET})
    client = ZammadClient(url=URL, http_token="test-token")

    result = client.merge_tickets(10, target_ticket_id=20)

    assert result["result"] == "success"
    api.ticket.find.assert_called_once_with(20)
    api.session.put.assert_called_once_with(MERGE_URL)


def test_merge_rejects_missing_target(api: Mock) -> None:
    client = ZammadClient(url=URL, http_token="test-token")
    with pytest.raises(ValueError, match="exactly one of"):
        client.merge_tickets(10)
    api.session.put.assert_not_called()


def test_merge_rejects_both_targets(api: Mock) -> None:
    client = ZammadClient(url=URL, http_token="test-token")
    with pytest.raises(ValueError, match="exactly one of"):
        client.merge_tickets(10, target_ticket_number="20002", target_ticket_id=20)
    api.session.put.assert_not_called()


def test_merge_propagates_http_error(api: Mock) -> None:
    api.session.put.return_value = _put_response({}, requests.HTTPError("403 Forbidden"))
    client = ZammadClient(url=URL, http_token="test-token")
    with pytest.raises(requests.HTTPError, match="403"):
        client.merge_tickets(10, target_ticket_number="20002")


def test_merge_raises_on_in_band_failure(api: Mock) -> None:
    """Zammad reports some merge failures with HTTP 200 and result != success."""
    api.session.put.return_value = _put_response({"result": "failed", "message": "Ticket already merged"})
    client = ZammadClient(url=URL, http_token="test-token")
    with pytest.raises(ValueError, match="Ticket already merged"):
        client.merge_tickets(10, target_ticket_number="20002")
