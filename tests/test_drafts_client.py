"""Tests for the draft-only ZammadClient methods against a controlled HTTP session.

No test reaches a real Zammad. The double is the transport under ResilientSession,
so every call arrives as ``request(METHOD, url, ...)``.
"""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from mcp_zammad.client import ZammadAPIError, ZammadClient
from mcp_zammad.models import TaskbarEntry

URL = "https://test.zammad.com/api/v1"


@pytest.fixture
def transport() -> Generator[Mock, None, None]:
    with patch("mcp_zammad.client.ZammadAPI") as mock_api:
        instance = Mock()
        mock_api.return_value = instance
        yield instance.session


@pytest.fixture
def client(transport: Mock) -> ZammadClient:  # the transport fixture patches ZammadAPI before the client is built
    return ZammadClient(url=URL, http_token="test-token")


def _resp(payload: object = None, status: int = 200, content: bytes | None = None) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    response.text = str(payload)
    response.content = b"x" if content is None else content
    return response


def _last(transport: Mock) -> tuple[str, str, dict]:
    args, kwargs = transport.request.call_args
    return args[0], args[1], kwargs


# (a) ticket shared draft


def test_get_ticket_shared_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp(
        {
            "shared_draft_id": 5,
            "assets": {
                "TicketSharedDraftZoom": {
                    "5": {"id": 5, "new_article": {"body": "<p>hi</p>"}, "ticket_attributes": {"state_id": 2}}
                }
            },
        }
    )
    result = client.get_ticket_shared_draft(12)
    assert result == {
        "shared_draft_id": 5,
        "new_article": {"body": "<p>hi</p>"},
        "ticket_attributes": {"state_id": 2},
    }
    method, url, _ = _last(transport)
    assert (method, url) == ("GET", f"{URL}/tickets/12/shared_draft")


def test_get_ticket_shared_draft_none(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": None, "assets": None})
    assert client.get_ticket_shared_draft(12) is None


def test_get_ticket_shared_draft_missing_asset(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 5, "assets": {}})
    result = client.get_ticket_shared_draft(12)
    assert result is not None
    assert result["new_article"] == {}


def test_get_ticket_shared_draft_404(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "Couldn't find Ticket"}, status=404)
    with pytest.raises(ZammadAPIError) as exc:
        client.get_ticket_shared_draft(999)
    assert exc.value.status_code == 404


def test_save_ticket_shared_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 7, "assets": {}})
    result = client.save_ticket_shared_draft(12, {"body": "x"}, {"state_id": 2}, form_id="f-1")
    assert result == {"shared_draft_id": 7}
    method, url, kwargs = _last(transport)
    assert (method, url) == ("PUT", f"{URL}/tickets/12/shared_draft")
    assert kwargs["json"] == {"new_article": {"body": "x"}, "ticket_attributes": {"state_id": 2}, "form_id": "f-1"}


def test_save_ticket_shared_draft_without_form_id(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 7})
    client.save_ticket_shared_draft(12, {}, {})
    assert "form_id" not in _last(transport)[2]["json"]


def test_save_ticket_shared_draft_403(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "forbidden"}, status=403)
    with pytest.raises(ZammadAPIError) as exc:
        client.save_ticket_shared_draft(12, {}, {})
    assert exc.value.status_code == 403


def test_delete_ticket_shared_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 7})
    assert client.delete_ticket_shared_draft(12) == {"shared_draft_id": 7}
    assert _last(transport)[:2] == ("DELETE", f"{URL}/tickets/12/shared_draft")


def test_delete_ticket_shared_draft_no_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "undefined method"}, status=500)
    with pytest.raises(ZammadAPIError) as exc:
        client.delete_ticket_shared_draft(12)
    assert exc.value.status_code == 500


# (b) new-ticket drafts


def test_list_new_ticket_drafts(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp(
        {
            "shared_draft_ids": [1, 2],
            "assets": {
                # Zammad keys assets by the app model name, without "::" (seen live 18 Nov 2026).
                "TicketSharedDraftStart": {
                    "1": {"id": 1, "name": "Rental", "group_id": 3},
                    "2": {"id": 2, "name": "Fine", "group_id": 4},
                }
            },
        }
    )
    assert client.list_new_ticket_drafts() == [
        {"id": 1, "name": "Rental", "group_id": 3},
        {"id": 2, "name": "Fine", "group_id": 4},
    ]
    assert _last(transport)[:2] == ("GET", f"{URL}/tickets/shared_drafts")


def test_list_new_ticket_drafts_ignores_class_name_key(client: ZammadClient, transport: Mock) -> None:
    """Only the exact asset key Zammad sends is read; a "::" spelling is not a fallback."""
    transport.request.return_value = _resp(
        {
            "shared_draft_ids": [5],
            "assets": {"Ticket::SharedDraftStart": {"5": {"id": 5, "name": "Old", "group_id": 2}}},
        }
    )
    assert client.list_new_ticket_drafts() == [{"id": 5, "name": None, "group_id": None}]


def test_list_new_ticket_drafts_missing_asset_gives_none(client: ZammadClient, transport: Mock) -> None:
    """An id with no asset record is still listed, with name and group None."""
    transport.request.return_value = _resp({"shared_draft_ids": [9], "assets": {}})
    assert client.list_new_ticket_drafts() == [{"id": 9, "name": None, "group_id": None}]


def test_list_new_ticket_drafts_empty(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_ids": [], "assets": {}})
    assert client.list_new_ticket_drafts() == []


def test_get_new_ticket_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp(
        {
            "shared_draft_id": 1,
            "shared_draft_content": {"title": "T", "body": "<p>b</p>"},
            "assets": {"TicketSharedDraftStart": {"1": {"id": 1, "name": "Rental", "group_id": 3}}},
        }
    )
    assert client.get_new_ticket_draft(1) == {
        "id": 1,
        "name": "Rental",
        "group_id": 3,
        "content": {"title": "T", "body": "<p>b</p>"},
    }
    assert _last(transport)[:2] == ("GET", f"{URL}/tickets/shared_drafts/1")


def test_get_new_ticket_draft_404(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "not found"}, status=404)
    with pytest.raises(ZammadAPIError) as exc:
        client.get_new_ticket_draft(99)
    assert exc.value.status_code == 404


def test_create_new_ticket_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 9, "assets": {}})
    result = client.create_new_ticket_draft("Rental", 3, {"body": "b"}, form_id="f-2")
    assert result == {"shared_draft_id": 9}
    method, url, kwargs = _last(transport)
    assert (method, url) == ("POST", f"{URL}/tickets/shared_drafts")
    assert kwargs["json"] == {"name": "Rental", "group_id": 3, "content": {"body": "b"}, "form_id": "f-2"}


def test_create_new_ticket_draft_422(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "Name can't be blank"}, status=422)
    with pytest.raises(ZammadAPIError) as exc:
        client.create_new_ticket_draft("", 3, {})
    assert exc.value.status_code == 422


def test_update_new_ticket_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 9})
    result = client.update_new_ticket_draft(9, "N", 3, {"body": "b"})
    assert result == {"shared_draft_id": 9}
    method, url, kwargs = _last(transport)
    assert (method, url) == ("PUT", f"{URL}/tickets/shared_drafts/9")
    assert "form_id" not in kwargs["json"]


def test_update_new_ticket_draft_with_form_id(client: ZammadClient, transport: Mock) -> None:
    """An update with attachments passes the upload cache's form_id, as the create does."""
    transport.request.return_value = _resp({"shared_draft_id": 9})
    client.update_new_ticket_draft(9, "N", 3, {"body": "b"}, form_id="f-123")
    method, url, kwargs = _last(transport)
    assert (method, url) == ("PUT", f"{URL}/tickets/shared_drafts/9")
    assert kwargs["json"] == {"name": "N", "group_id": 3, "content": {"body": "b"}, "form_id": "f-123"}


def test_delete_new_ticket_draft(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"shared_draft_id": 9})
    assert client.delete_new_ticket_draft(9) == {"shared_draft_id": 9}
    assert _last(transport)[:2] == ("DELETE", f"{URL}/tickets/shared_drafts/9")


def test_delete_new_ticket_draft_404(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "nf"}, status=404)
    with pytest.raises(ZammadAPIError):
        client.delete_new_ticket_draft(9)


# (c) upload cache


def test_upload_cache_add(client: ZammadClient, transport: Mock, tmp_path: Path) -> None:
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF")
    transport.request.return_value = _resp(
        {"success": True, "data": {"id": 4, "filename": "scan.pdf", "size": "4", "contentType": "application/pdf"}}
    )
    result = client.upload_cache_add("form-1", str(f))
    assert result["id"] == 4
    assert result["filename"] == "scan.pdf"
    method, url, kwargs = _last(transport)
    assert (method, url) == ("POST", f"{URL}/upload_caches/form-1")
    name, _handle = kwargs["files"]["File"]
    assert name == "scan.pdf"
    assert "json" not in kwargs


def test_upload_cache_add_encodes_form_id(client: ZammadClient, transport: Mock, tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("a")
    transport.request.return_value = _resp({"success": True, "data": {}})
    client.upload_cache_add("../x?y", str(f))
    assert _last(transport)[1] == f"{URL}/upload_caches/..%2Fx%3Fy"


def test_upload_cache_add_missing_file(client: ZammadClient, transport: Mock, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        client.upload_cache_add("form-1", str(tmp_path / "nope.pdf"))
    transport.request.assert_not_called()


def test_upload_cache_add_error(client: ZammadClient, transport: Mock, tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("a")
    transport.request.return_value = _resp({"error": "too large"}, status=413)
    with pytest.raises(ZammadAPIError) as exc:
        client.upload_cache_add("form-1", str(f))
    assert exc.value.status_code == 413


def test_upload_cache_delete_one_item(client: ZammadClient, transport: Mock) -> None:
    """With item_id only that cached file is removed, not the whole cache of the form."""
    transport.request.return_value = _resp({"success": True})
    assert client.upload_cache_delete("form-1", item_id=5) == {"success": True}
    assert _last(transport)[:2] == ("DELETE", f"{URL}/upload_caches/form-1/items/5")


def test_upload_cache_delete(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"success": True})
    assert client.upload_cache_delete("form-1") == {"success": True}
    assert _last(transport)[:2] == ("DELETE", f"{URL}/upload_caches/form-1")


# (d) taskbar


def test_list_taskbar(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp([{"id": 1, "key": "Ticket-12"}])
    assert client.list_taskbar() == [{"id": 1, "key": "Ticket-12"}]
    assert _last(transport)[:2] == ("GET", f"{URL}/taskbar")


def test_list_taskbar_unexpected_shape(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"oops": 1})
    assert client.list_taskbar() == []


def test_list_taskbar_404(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"error": "nf"}, status=404)
    with pytest.raises(ZammadAPIError) as exc:
        client.list_taskbar()
    assert exc.value.status_code == 404


def test_create_taskbar(client: ZammadClient, transport: Mock) -> None:
    entry = TaskbarEntry(key="Ticket-12", callback="TicketZoom", params={"ticket_id": 12}).model_dump()
    transport.request.return_value = _resp({"id": 3, **entry})
    result = client.create_taskbar(entry)
    assert result["id"] == 3
    method, url, kwargs = _last(transport)
    assert (method, url) == ("POST", f"{URL}/taskbar")
    assert kwargs["json"]["app"] == "desktop"


def test_update_taskbar(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp({"id": 3})
    client.update_taskbar(3, {"state": {"article": {"body": "y"}}})
    method, url, kwargs = _last(transport)
    assert (method, url) == ("PUT", f"{URL}/taskbar/3")
    assert kwargs["json"] == {"state": {"article": {"body": "y"}}}


def test_update_taskbar_422(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp("bad", status=422)
    transport.request.return_value.json.side_effect = ValueError
    transport.request.return_value.text = "bad"
    with pytest.raises(ZammadAPIError) as exc:
        client.update_taskbar(3, {})
    assert exc.value.body == "bad"


def test_empty_and_malformed_success_bodies(client: ZammadClient, transport: Mock) -> None:
    transport.request.return_value = _resp(None, status=204, content=b"")
    assert client.delete_new_ticket_draft(1) == {"shared_draft_id": None}
    bad = _resp(None)
    bad.json.side_effect = ValueError
    transport.request.return_value = bad
    with pytest.raises(ZammadAPIError):
        client.list_taskbar()


# models


def test_models_reject_bad_input() -> None:
    with pytest.raises(ValidationError):
        TaskbarEntry(key="k", callback="c", unknown=1)  # type: ignore[call-arg]
