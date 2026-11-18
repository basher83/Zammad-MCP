"""Tests for the draft-only MCP tools. The client is a mock; nothing reaches a Zammad server."""

import re
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client
from pydantic import ValidationError

from mcp_zammad.client import ZammadClient
from mcp_zammad.server import DEFAULT_ATTACHMENT_MAX_BYTES, ZammadMCPServer

DRAFT_TOOLS = [
    "zammad_get_ticket_shared_draft",
    "zammad_save_ticket_shared_draft",
    "zammad_delete_ticket_shared_draft",
    "zammad_list_new_ticket_drafts",
    "zammad_get_new_ticket_draft",
    "zammad_save_new_ticket_draft",
    "zammad_delete_new_ticket_draft",
    "zammad_get_reply_in_progress",
    "zammad_save_reply_in_progress",
]


def _group(group_id: int, name: str) -> dict[str, Any]:
    """A group as Zammad returns it; the server builds a Group model from every entry."""
    return {"id": group_id, "name": name, "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"}


class _PagedGroupResource:
    """Fake of the zammad_py group resource: it slices pages like Zammad, and per_page defaults to 10."""

    def __init__(self, groups: list[dict[str, Any]]) -> None:
        self._groups = groups

    def all(self, page: int = 1, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = filters or {}
        page = params.get("page", page)
        per_page = params.get("per_page", 10)
        start = (page - 1) * per_page
        return self._groups[start : start + per_page]


@pytest.fixture
def client() -> Mock:
    """A mock with the real client's method names. Touching ``api`` raises, so no article path can hide."""
    mock = Mock(spec=ZammadClient)
    mock.upload_cache_add.side_effect = lambda _form_id, path: {"id": 1, "filename": Path(path).name}
    mock.get_ticket.return_value = {"id": 7, "title": "Ticket title", "articles": []}
    return mock


@pytest.fixture
def tools(client: Mock, decorator_capturer) -> dict[str, Any]:
    with patch("mcp_zammad.server.ZammadClient"):
        server = ZammadMCPServer()
    server.client = client
    captured, wrapper = decorator_capturer(server.mcp.tool)
    server.mcp.tool = wrapper  # type: ignore[method-assign, assignment]
    server.get_client = lambda: client  # type: ignore[method-assign, assignment, return-value]
    server._setup_tools()
    return captured


@pytest.fixture
def pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ZAMMAD_ATTACHMENT_DIR", str(tmp_path))
    monkeypatch.delenv("ZAMMAD_ATTACHMENT_MAX_BYTES", raising=False)
    path = tmp_path / "offer.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


def test_all_nine_tools_registered_and_none_sends(tools: dict[str, Any]) -> None:
    for name in DRAFT_TOOLS:
        assert name in tools
    draft_like = {n for n in tools if "draft" in n or "reply_in_progress" in n}
    assert draft_like == set(DRAFT_TOOLS)
    assert not any(word in n for n in draft_like for word in ("send", "submit", "article"))


def test_get_ticket_shared_draft(tools: dict[str, Any], client: Mock) -> None:
    client.get_ticket_shared_draft.return_value = {
        "shared_draft_id": 5,
        "new_article": {"body": "x"},
        "ticket_attributes": {},
    }
    result = tools["zammad_get_ticket_shared_draft"](ticket_id=7)
    client.get_ticket_shared_draft.assert_called_once_with(7)
    assert result["exists"] is True
    assert result["shared_draft_id"] == 5


def test_get_ticket_shared_draft_none(tools: dict[str, Any], client: Mock) -> None:
    client.get_ticket_shared_draft.return_value = None
    assert tools["zammad_get_ticket_shared_draft"](ticket_id=7) == {"exists": False}


def test_save_ticket_shared_draft_escapes_plain_text(tools: dict[str, Any], client: Mock) -> None:
    client.save_ticket_shared_draft.return_value = {"shared_draft_id": 9}
    result = tools["zammad_save_ticket_shared_draft"](
        ticket_id=7, body="a <b> & c\nline2", content_type="text/plain", to="x@example.com", subject="Re: x"
    )
    ticket_id, new_article, attrs = client.save_ticket_shared_draft.call_args.args
    assert ticket_id == 7
    assert new_article["body"] == "a &lt;b&gt; &amp; c<br>line2"
    assert new_article["content_type"] == "text/html"
    assert new_article["type"] == "email"
    assert new_article["internal"] is False
    assert new_article["to"] == "x@example.com"
    assert "cc" not in new_article
    assert attrs == {}
    assert result == {"shared_draft_id": 9, "attachments": 0}
    client.upload_cache_add.assert_not_called()


def test_save_ticket_shared_draft_html_kept(tools: dict[str, Any], client: Mock) -> None:
    client.save_ticket_shared_draft.return_value = {"shared_draft_id": 9}
    tools["zammad_save_ticket_shared_draft"](ticket_id=7, body="<p>hi</p>", content_type="text/html")
    assert client.save_ticket_shared_draft.call_args.args[1]["body"] == "<p>hi</p>"


def test_save_ticket_shared_draft_uploads_before_draft_write(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    client.save_ticket_shared_draft.return_value = {"shared_draft_id": 9}
    order = Mock()
    order.attach_mock(client.upload_cache_add, "upload")
    order.attach_mock(client.save_ticket_shared_draft, "save")
    result = tools["zammad_save_ticket_shared_draft"](ticket_id=7, body="hi", attachments=[str(pdf)])
    assert [c[0] for c in order.mock_calls] == ["upload", "save"]
    form_id = client.upload_cache_add.call_args.args[0]
    assert client.upload_cache_add.call_args.args[1] == str(pdf)
    assert client.save_ticket_shared_draft.call_args.kwargs["form_id"] == form_id
    assert client.save_ticket_shared_draft.call_args.args[1]["form_id"] == form_id
    assert result["attachments"] == 1


def test_save_ticket_shared_draft_missing_file_writes_nothing(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        tools["zammad_save_ticket_shared_draft"](ticket_id=7, body="hi", attachments=[str(pdf), str(pdf) + ".nope"])
    client.upload_cache_add.assert_not_called()
    client.save_ticket_shared_draft.assert_not_called()


def test_relative_attachment_path_rejected(tools: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        tools["zammad_save_ticket_shared_draft"](ticket_id=7, body="hi", attachments=["offer.pdf"])


def test_delete_ticket_shared_draft(tools: dict[str, Any], client: Mock) -> None:
    client.delete_ticket_shared_draft.return_value = {"shared_draft_id": 5}
    assert tools["zammad_delete_ticket_shared_draft"](ticket_id=7) == {"shared_draft_id": 5}
    client.delete_ticket_shared_draft.assert_called_once_with(7)


def test_list_new_ticket_drafts_filters_by_group_name(tools: dict[str, Any], client: Mock) -> None:
    client.list_new_ticket_drafts.return_value = [
        {"id": 1, "name": "a", "group_id": 2},
        {"id": 2, "name": "b", "group_id": 3},
    ]
    client.get_groups.return_value = [_group(2, "Users"), _group(3, "Sales")]
    assert tools["zammad_list_new_ticket_drafts"](group="sales") == [{"id": 2, "name": "b", "group_id": 3}]
    assert len(tools["zammad_list_new_ticket_drafts"]()) == 2


def test_get_new_ticket_draft(tools: dict[str, Any], client: Mock) -> None:
    client.get_new_ticket_draft.return_value = {"id": 4, "name": "n", "group_id": 2, "content": {"title": "t"}}
    assert tools["zammad_get_new_ticket_draft"](draft_id=4)["content"] == {"title": "t"}
    client.get_new_ticket_draft.assert_called_once_with(4)


def test_save_new_ticket_draft_creates(tools: dict[str, Any], client: Mock) -> None:
    client.get_groups.return_value = [_group(2, "Users")]
    client.search_users.return_value = [{"id": 11, "email": "Cust@Example.com"}]
    client.create_new_ticket_draft.return_value = {"shared_draft_id": 6}
    result = tools["zammad_save_new_ticket_draft"](
        name="Offer",
        group="Users",
        title="Hire",
        customer="cust@example.com",
        to="cust@example.com",
        subject="Hire",
        body="line1\nline2",
        content_type="text/plain",
    )
    name, group_id, content = client.create_new_ticket_draft.call_args.args
    assert (name, group_id) == ("Offer", 2)
    assert content == {
        "formSenderType": "email-out",
        "customer_id": 11,
        "customer_id_completion": "Cust@Example.com",
        "title": "Hire",
        "to": "cust@example.com",
        "subject": "Hire",
        "body": "line1<br>line2",
    }
    assert client.create_new_ticket_draft.call_args.kwargs["form_id"] is None
    client.update_new_ticket_draft.assert_not_called()
    assert result == {"shared_draft_id": 6, "attachments": 0}


def test_save_new_ticket_draft_numeric_group_and_customer(tools: dict[str, Any], client: Mock) -> None:
    client.get_user.return_value = {"id": 11, "email": "c@example.com"}
    client.create_new_ticket_draft.return_value = {"shared_draft_id": 6}
    tools["zammad_save_new_ticket_draft"](name="n", group="2", customer="11", article_type="phone-in")
    _, group_id, content = client.create_new_ticket_draft.call_args.args
    assert group_id == 2
    assert content["customer_id"] == 11
    assert content["formSenderType"] == "phone-in"
    client.get_groups.assert_not_called()


def test_save_new_ticket_draft_updates_with_attachment_upload_first(
    tools: dict[str, Any], client: Mock, pdf: Path
) -> None:
    client.update_new_ticket_draft.return_value = {"shared_draft_id": 6}
    order = Mock()
    order.attach_mock(client.upload_cache_add, "upload")
    order.attach_mock(client.update_new_ticket_draft, "update")
    result = tools["zammad_save_new_ticket_draft"](name="n", group="2", attachments=[str(pdf)], draft_id=6)
    assert [c[0] for c in order.mock_calls] == ["upload", "update"]
    assert client.update_new_ticket_draft.call_args.args[0] == 6
    assert client.update_new_ticket_draft.call_args.kwargs["form_id"] == client.upload_cache_add.call_args.args[0]
    client.create_new_ticket_draft.assert_not_called()
    assert result["attachments"] == 1


def test_save_new_ticket_draft_unknown_group_and_customer(tools: dict[str, Any], client: Mock) -> None:
    client.get_groups.return_value = []
    with pytest.raises(ValueError, match="Group"):
        tools["zammad_save_new_ticket_draft"](name="n", group="Nope")
    client.search_users.return_value = []
    with pytest.raises(ValueError, match="Customer"):
        tools["zammad_save_new_ticket_draft"](name="n", group="2", customer="x@example.com")
    client.create_new_ticket_draft.assert_not_called()


def test_delete_new_ticket_draft(tools: dict[str, Any], client: Mock) -> None:
    client.delete_new_ticket_draft.return_value = {"shared_draft_id": 4}
    assert tools["zammad_delete_new_ticket_draft"](draft_id=4) == {"shared_draft_id": 4}
    client.delete_new_ticket_draft.assert_called_once_with(4)


def test_get_reply_in_progress_found_and_missing(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = [
        {"id": 1, "key": "Ticket-8", "app": "desktop", "state": {"article": {"body": "other"}}},
        {"id": 2, "key": "Ticket-7", "app": "desktop", "state": {"article": {"body": "<p>mine</p>", "type": "email"}}},
    ]
    assert tools["zammad_get_reply_in_progress"](ticket_id=7) == {
        "exists": True,
        "taskbar_id": 2,
        "article": {"body": "<p>mine</p>", "type": "email"},
    }
    assert tools["zammad_get_reply_in_progress"](ticket_id=99) == {"exists": False}


def test_save_reply_in_progress_creates_entry_when_ticket_not_open(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = []
    client.create_taskbar.return_value = {"id": 12}
    result = tools["zammad_save_reply_in_progress"](ticket_id=7, body="a & b", to="x@example.com")
    entry = client.create_taskbar.call_args.args[0]
    assert entry["key"] == "Ticket-7"
    assert entry["callback"] == "TicketZoom"
    assert entry["params"]["ticket_id"] == 7
    assert entry["state"]["article"]["body"] == "a &amp; b"
    assert entry["state"]["article"]["to"] == "x@example.com"
    assert entry["state"]["article"]["type"] == "email"
    client.update_taskbar.assert_not_called()
    assert result == {"taskbar_id": 12, "created": True}


def test_save_reply_in_progress_updates_and_keeps_other_state(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = [
        {
            "id": 2,
            "key": "Ticket-7",
            "app": "desktop",
            "state": {"ticket": {"state_id": 2}, "article": {"cc": "keep@example.com"}},
        }
    ]
    client.update_taskbar.return_value = {"id": 2}
    result = tools["zammad_save_reply_in_progress"](ticket_id=7, body="<p>x</p>", content_type="text/html", type="note")
    taskbar_id, entry = client.update_taskbar.call_args.args
    assert taskbar_id == 2
    assert entry["state"]["ticket"] == {"state_id": 2}
    assert entry["state"]["article"] == {"cc": "keep@example.com", "body": "<p>x</p>", "type": "note"}
    client.create_taskbar.assert_not_called()
    assert result == {"taskbar_id": 2, "created": False}


@pytest.mark.parametrize("name", DRAFT_TOOLS)
def test_no_tool_touches_article_create_or_raw_api(tools: dict[str, Any], client: Mock, name: str, pdf: Path) -> None:
    """Run every tool; the spec'd mock forbids ``api`` and add_article/create_ticket must stay unused."""
    client.get_ticket_shared_draft.return_value = None
    client.save_ticket_shared_draft.return_value = {}
    client.delete_ticket_shared_draft.return_value = {}
    client.list_new_ticket_drafts.return_value = []
    client.get_new_ticket_draft.return_value = {}
    client.create_new_ticket_draft.return_value = {}
    client.delete_new_ticket_draft.return_value = {}
    client.list_taskbar.return_value = []
    client.create_taskbar.return_value = {}
    args: dict[str, dict[str, Any]] = {
        "zammad_get_ticket_shared_draft": {"ticket_id": 1},
        "zammad_save_ticket_shared_draft": {"ticket_id": 1, "body": "b", "attachments": [str(pdf)]},
        "zammad_delete_ticket_shared_draft": {"ticket_id": 1},
        "zammad_list_new_ticket_drafts": {},
        "zammad_get_new_ticket_draft": {"draft_id": 1},
        "zammad_save_new_ticket_draft": {"name": "n", "group": "1", "attachments": [str(pdf)]},
        "zammad_delete_new_ticket_draft": {"draft_id": 1},
        "zammad_get_reply_in_progress": {"ticket_id": 1},
        "zammad_save_reply_in_progress": {"ticket_id": 1, "body": "b"},
    }
    tools[name](**args[name])
    for forbidden in ("add_article", "create_ticket", "update_ticket", "merge_tickets"):
        getattr(client, forbidden).assert_not_called()


def _pdf_entry(client: Mock, article: dict[str, Any] | None) -> None:
    state = {"article": article} if article is not None else {}
    client.list_taskbar.return_value = [{"id": 2, "key": "Ticket-7", "app": "desktop", "state": state}]
    client.update_taskbar.return_value = {"id": 2}


def test_reply_attachments_upload_before_taskbar_write(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    _pdf_entry(client, None)
    order = Mock()
    order.attach_mock(client.upload_cache_add, "upload")
    order.attach_mock(client.update_taskbar, "write")
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", attachments=[str(pdf)])
    assert [c[0] for c in order.mock_calls] == ["upload", "write"]


def test_reply_attachments_reuse_existing_form_id_and_merge(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    old = {"id": 5, "filename": "old.pdf"}
    _pdf_entry(client, {"form_id": "abc", "attachments": [old]})
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", attachments=[str(pdf)])
    assert client.upload_cache_add.call_args.args[0] == "abc"
    article = client.update_taskbar.call_args.args[1]["state"]["article"]
    assert article["form_id"] == "abc"
    assert article["attachments"] == [old, {"id": 1, "filename": pdf.name}]


def test_reply_attachments_new_uuid_when_no_form_id(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    client.list_taskbar.return_value = []
    client.create_taskbar.return_value = {"id": 3}
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", attachments=[str(pdf)])
    form_id = client.upload_cache_add.call_args.args[0]
    assert uuid.UUID(form_id).version == 4
    article = client.create_taskbar.call_args.args[0]["state"]["article"]
    assert article["form_id"] == form_id
    assert article["attachments"] == [{"id": 1, "filename": pdf.name}]


def test_reply_without_attachments_has_no_form_id(tools: dict[str, Any], client: Mock) -> None:
    _pdf_entry(client, {"cc": "k@example.com"})
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x")
    client.upload_cache_add.assert_not_called()
    article = client.update_taskbar.call_args.args[1]["state"]["article"]
    assert article == {"cc": "k@example.com", "body": "x"}


# --- attachment confinement and size cap (finding 1) -------------------------


def _save_with(tools: dict[str, Any], *paths: Path) -> Any:
    return tools["zammad_save_ticket_shared_draft"](ticket_id=7, body="hi", attachments=[str(p) for p in paths])


def test_attachments_disabled_without_dir(
    tools: dict[str, Any], client: Mock, pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ZAMMAD_ATTACHMENT_DIR")
    with pytest.raises(ValueError, match="ZAMMAD_ATTACHMENT_DIR is not set"):
        _save_with(tools, pdf)
    client.upload_cache_add.assert_not_called()
    client.save_ticket_shared_draft.assert_not_called()


def test_attachment_outside_dir_rejected(
    tools: dict[str, Any], client: Mock, pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("ZAMMAD_ATTACHMENT_DIR", str(allowed))
    with pytest.raises(ValueError, match="outside"):
        _save_with(tools, pdf)
    client.upload_cache_add.assert_not_called()


def test_attachment_symlink_escape_rejected(
    tools: dict[str, Any], client: Mock, pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    link = allowed / "innocent.pdf"
    link.symlink_to(pdf)
    monkeypatch.setenv("ZAMMAD_ATTACHMENT_DIR", str(allowed))
    with pytest.raises(ValueError, match="outside"):
        _save_with(tools, link)
    client.upload_cache_add.assert_not_called()


def test_attachment_inside_dir_uploads_resolved_path(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    client.save_ticket_shared_draft.return_value = {"shared_draft_id": 9}
    assert _save_with(tools, pdf)["attachments"] == 1
    assert client.upload_cache_add.call_args.args[1] == str(pdf.resolve())


def test_attachment_over_default_cap_rejected_before_upload(
    tools: dict[str, Any], client: Mock, pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_zammad.server.DEFAULT_ATTACHMENT_MAX_BYTES", 5)
    with pytest.raises(ValueError, match="exceeds"):
        _save_with(tools, pdf)
    client.upload_cache_add.assert_not_called()


def test_attachment_cap_from_env(
    tools: dict[str, Any], client: Mock, pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZAMMAD_ATTACHMENT_MAX_BYTES", "5")
    with pytest.raises(ValueError, match="ZAMMAD_ATTACHMENT_MAX_BYTES"):
        _save_with(tools, pdf)
    monkeypatch.setenv("ZAMMAD_ATTACHMENT_MAX_BYTES", "lots")
    with pytest.raises(ValueError, match="ZAMMAD_ATTACHMENT_MAX_BYTES"):
        _save_with(tools, pdf)
    client.upload_cache_add.assert_not_called()


def test_default_attachment_cap_is_10_mib() -> None:
    assert DEFAULT_ATTACHMENT_MAX_BYTES == 10485760


# --- upload cache cleanup on failure (finding 3) -----------------------------


def test_second_upload_failure_deletes_first_item(
    tools: dict[str, Any], client: Mock, pdf: Path, tmp_path: Path
) -> None:
    other = tmp_path / "b.pdf"
    other.write_bytes(b"%PDF-1.4 b")
    client.upload_cache_add.side_effect = [{"id": 11, "filename": "offer.pdf"}, RuntimeError("boom")]
    with pytest.raises(RuntimeError, match="boom"):
        _save_with(tools, pdf, other)
    form_id = client.upload_cache_add.call_args_list[0].args[0]
    client.upload_cache_delete.assert_called_once_with(form_id, item_id=11)
    client.save_ticket_shared_draft.assert_not_called()


def test_draft_write_failure_deletes_uploaded_items(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    client.upload_cache_add.side_effect = None
    client.upload_cache_add.return_value = {"id": 12, "filename": "offer.pdf"}
    client.save_ticket_shared_draft.side_effect = RuntimeError("write failed")
    with pytest.raises(RuntimeError, match="write failed"):
        _save_with(tools, pdf)
    form_id = client.upload_cache_add.call_args.args[0]
    client.upload_cache_delete.assert_called_once_with(form_id, item_id=12)


def test_reply_taskbar_failure_deletes_only_new_items(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    old = {"id": 5, "filename": "old.pdf"}
    _pdf_entry(client, {"form_id": "abc", "attachments": [old]})
    client.update_taskbar.side_effect = RuntimeError("taskbar down")
    with pytest.raises(RuntimeError, match="taskbar down"):
        tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", attachments=[str(pdf)])
    client.upload_cache_delete.assert_called_once_with("abc", item_id=1)


def test_cleanup_failure_does_not_mask_original_error(tools: dict[str, Any], client: Mock, pdf: Path) -> None:
    client.save_ticket_shared_draft.side_effect = RuntimeError("write failed")
    client.upload_cache_delete.side_effect = RuntimeError("cleanup failed")
    with pytest.raises(RuntimeError, match="write failed"):
        _save_with(tools, pdf)
    client.upload_cache_delete.assert_called_once()


# --- reply in progress: internal flag and omitted fields (finding 2) ----------


def test_new_reply_entry_is_a_public_email_by_default(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = []
    client.create_taskbar.return_value = {"id": 12}
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x")
    article = client.create_taskbar.call_args.args[0]["state"]["article"]
    assert article["type"] == "email"
    assert article["internal"] is False


def test_new_reply_entry_can_be_an_internal_note(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = []
    client.create_taskbar.return_value = {"id": 12}
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", type="note", internal=True)
    article = client.create_taskbar.call_args.args[0]["state"]["article"]
    assert article["type"] == "note"
    assert article["internal"] is True


def test_existing_internal_note_keeps_type_and_flag_when_omitted(tools: dict[str, Any], client: Mock) -> None:
    _pdf_entry(client, {"type": "note", "internal": True, "body": "old"})
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="new")
    article = client.update_taskbar.call_args.args[1]["state"]["article"]
    assert article["type"] == "note"
    assert article["internal"] is True
    assert article["body"] == "new"


def test_existing_entry_switches_internal_flag_when_given(tools: dict[str, Any], client: Mock) -> None:
    _pdf_entry(client, {"type": "note", "internal": True})
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", internal=False)
    article = client.update_taskbar.call_args.args[1]["state"]["article"]
    assert article["internal"] is False
    assert article["type"] == "note"


# --- replacing saves are destructive and say so (finding 4) -------------------

REPLACING_SAVE_TOOLS = [
    "zammad_save_ticket_shared_draft",
    "zammad_save_new_ticket_draft",
    "zammad_save_reply_in_progress",
]


@pytest.mark.asyncio
async def test_replacing_save_tools_are_destructive_and_say_replaces() -> None:
    with patch("mcp_zammad.server.ZammadClient", return_value=Mock()):
        server = ZammadMCPServer()
        async with Client(server.mcp) as mcp_client:
            listed = {tool.name: tool for tool in await mcp_client.list_tools()}
    for name in REPLACING_SAVE_TOOLS:
        assert listed[name].annotations is not None
        assert listed[name].annotations.destructiveHint is True, name
        assert "replaces" in (listed[name].description or ""), name


# --- content_type defaults to plain text on every draft tool (finding 6) ------


def test_shared_draft_plain_text_is_the_default(tools: dict[str, Any], client: Mock) -> None:
    client.save_ticket_shared_draft.return_value = {"shared_draft_id": 9}
    tools["zammad_save_ticket_shared_draft"](ticket_id=7, body="a <b> & c")
    assert client.save_ticket_shared_draft.call_args.args[1]["body"] == "a &lt;b&gt; &amp; c"


def test_new_ticket_draft_plain_text_is_the_default(tools: dict[str, Any], client: Mock) -> None:
    client.create_new_ticket_draft.return_value = {"shared_draft_id": 6}
    tools["zammad_save_new_ticket_draft"](name="n", group="2", body="a <b>")
    _, _, content = client.create_new_ticket_draft.call_args.args
    assert content["body"] == "a &lt;b&gt;"


# --- reply taskbar lookup is the desktop entry only (finding 8) ---------------


def test_reply_lookup_ignores_mobile_taskbar_entries(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = [
        {"id": 4, "key": "Ticket-7", "app": "mobile", "state": {"article": {"body": "phone"}}},
    ]
    assert tools["zammad_get_reply_in_progress"](ticket_id=7) == {"exists": False}


def test_save_skips_mobile_entry_and_creates_desktop_entry(tools: dict[str, Any], client: Mock) -> None:
    client.list_taskbar.return_value = [
        {"id": 4, "key": "Ticket-7", "app": "mobile", "state": {"article": {"form_id": "phone", "body": "p"}}},
    ]
    client.create_taskbar.return_value = {"id": 12}
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x")
    client.update_taskbar.assert_not_called()
    assert client.create_taskbar.call_args.args[0]["app"] == "desktop"


def _zammad_email_search(users: list[dict[str, Any]]):
    """A fake of the Zammad user search: reads ``email:"..."`` phrases and returns case-insensitive exact matches."""
    phrase = re.compile(r'^email:"((?:[^"\\]|\\.)*)"$')

    def search(query: str, page: int = 1, per_page: int = 25) -> list[dict[str, Any]]:
        match = phrase.match(query)
        if match is None or per_page < 50:
            return []
        wanted = re.sub(r"\\(.)", r"\1", match.group(1)).lower()
        return [user for user in users if str(user["email"]).lower() == wanted]

    return search


def test_save_new_ticket_draft_finds_customer_with_plus_and_dot_in_email(tools: dict[str, Any], client: Mock) -> None:
    client.get_groups.return_value = [_group(2, "Users")]
    client.search_users.side_effect = _zammad_email_search([{"id": 21, "email": "Jane.Doe+offers@Example.com"}])
    client.create_new_ticket_draft.return_value = {"shared_draft_id": 6}
    tools["zammad_save_new_ticket_draft"](name="n", group="Users", customer="jane.doe+offers@example.com")
    _, _, content = client.create_new_ticket_draft.call_args.args
    assert content["customer_id"] == 21
    assert content["customer_id_completion"] == "Jane.Doe+offers@Example.com"


def test_save_new_ticket_draft_names_email_when_customer_not_found(tools: dict[str, Any], client: Mock) -> None:
    client.get_groups.return_value = [_group(2, "Users")]
    client.search_users.side_effect = _zammad_email_search([{"id": 21, "email": "other@example.com"}])
    with pytest.raises(ValueError, match=r"jane\.doe\+offers@example\.com"):
        tools["zammad_save_new_ticket_draft"](name="n", group="Users", customer="jane.doe+offers@example.com")
    client.create_new_ticket_draft.assert_not_called()


@pytest.fixture
def paged_groups(client: Mock) -> Mock:
    """Route the mock's get_groups through the real paginated client, served by a fake api.group of 12 groups."""
    with patch("mcp_zammad.client.ZammadAPI") as api:
        api.return_value.group = _PagedGroupResource([_group(i, f"Group {i}") for i in range(1, 13)])
        real = ZammadClient(url="https://zammad.example/api/v1", http_token="test-token")
    client.get_groups.side_effect = real.get_groups
    return client


def test_save_new_ticket_draft_finds_group_after_the_first_page(tools: dict[str, Any], paged_groups: Mock) -> None:
    paged_groups.create_new_ticket_draft.return_value = {"shared_draft_id": 6}
    tools["zammad_save_new_ticket_draft"](name="n", group="group 11")
    assert paged_groups.create_new_ticket_draft.call_args.args[1] == 11


def test_group_lookups_share_one_cached_group_list(tools: dict[str, Any], client: Mock) -> None:
    client.get_groups.return_value = [_group(2, "Users"), _group(3, "Sales")]
    client.create_new_ticket_draft.return_value = {"shared_draft_id": 6}
    tools["zammad_save_new_ticket_draft"](name="a", group="Sales")
    tools["zammad_save_new_ticket_draft"](name="b", group="Users")
    assert client.get_groups.call_count == 1


# --- reply in progress: reply_to_article_id fills the reply like the desktop Reply button (S6) ---


def _article(article_id: int, **fields: Any) -> dict[str, Any]:
    """A ticket article as Zammad returns it; a customer email unless ``fields`` say otherwise."""
    base: dict[str, Any] = {
        "id": article_id,
        "sender": "Customer",
        "type": "email",
        "from": f"customer{article_id}@example.com",
        "to": "support@example.com",
        "cc": "",
        "reply_to": None,
        "subject": f"Question {article_id}",
        "message_id": f"<msg{article_id}@example.com>",
    }
    return {**base, **fields}


def _reply_article(tools: dict[str, Any], client: Mock, articles: list[dict[str, Any]], **args: Any) -> dict[str, Any]:
    """Save a reply on ticket 7 whose articles are ``articles``; return the reply-box article written."""
    client.get_ticket.return_value = {"id": 7, "title": "Ticket title", "articles": articles}
    client.list_taskbar.return_value = []
    client.create_taskbar.return_value = {"id": 12}
    tools["zammad_save_reply_in_progress"](ticket_id=7, body="x", **args)
    return client.create_taskbar.call_args.args[0]["state"]["article"]


def test_reply_defaults_to_latest_customer_email(tools: dict[str, Any], client: Mock) -> None:
    articles = [
        _article(2),
        _article(3, sender="Customer", type="note"),
        _article(4, sender="Agent"),
        _article(5, **{"from": "latest@example.com"}, message_id="<latest@example.com>"),
    ]
    article = _reply_article(tools, client, articles)
    assert article["to"] == "latest@example.com"
    assert article["in_reply_to"] == "<latest@example.com>"
    assert article["subtype"] == "reply"
    assert article["type"] == "email"


def test_reply_to_article_id_fills_from_that_article(tools: dict[str, Any], client: Mock) -> None:
    articles = [
        _article(2, cc="team@example.com", subject="Invoice", **{"from": "old@example.com"}),
        _article(5, **{"from": "latest@example.com"}),
    ]
    article = _reply_article(tools, client, articles, reply_to_article_id=2)
    assert article["to"] == "old@example.com"
    assert article["cc"] == "team@example.com"
    assert article["subject"] == "Invoice"
    assert article["in_reply_to"] == "<msg2@example.com>"
    assert article["subtype"] == "reply"
    assert article["type"] == "email"


def test_reply_to_uses_reply_to_before_from(tools: dict[str, Any], client: Mock) -> None:
    articles = [_article(2, reply_to="replies@example.com")]
    article = _reply_article(tools, client, articles, reply_to_article_id=2)
    assert article["to"] == "replies@example.com"


def test_reply_to_an_agent_email_goes_to_its_recipient(tools: dict[str, Any], client: Mock) -> None:
    articles = [
        _article(2, sender="Agent", to="customer@example.com", **{"from": "Agent via Support <support@example.com>"})
    ]
    article = _reply_article(tools, client, articles, reply_to_article_id=2)
    assert article["to"] == "customer@example.com"


def test_reply_keeps_ticket_title_when_article_subject_is_empty(tools: dict[str, Any], client: Mock) -> None:
    articles = [_article(2, subject="")]
    article = _reply_article(tools, client, articles, reply_to_article_id=2)
    assert article["subject"] == "Ticket title"


def test_explicit_to_cc_subject_win_over_filled_values(tools: dict[str, Any], client: Mock) -> None:
    articles = [_article(2, cc="team@example.com", subject="Invoice")]
    article = _reply_article(
        tools,
        client,
        articles,
        reply_to_article_id=2,
        to="given@example.com",
        cc="given-cc@example.com",
        subject="Mine",
    )
    assert article["to"] == "given@example.com"
    assert article["cc"] == "given-cc@example.com"
    assert article["subject"] == "Mine"
    assert article["in_reply_to"] == "<msg2@example.com>"


@pytest.mark.parametrize(
    "articles, article_id",
    [
        ([_article(2, type="note", sender="Agent")], 2),
        ([_article(2)], 99),
    ],
    ids=["internal-note", "not-on-ticket"],
)
def test_reply_to_article_id_must_be_an_email_article_of_the_ticket(
    tools: dict[str, Any], client: Mock, pdf: Path, articles: list[dict[str, Any]], article_id: int
) -> None:
    client.get_ticket.return_value = {"id": 7, "title": "Ticket title", "articles": articles}
    with pytest.raises(ValueError, match="email article"):
        tools["zammad_save_reply_in_progress"](
            ticket_id=7, body="x", reply_to_article_id=article_id, attachments=[str(pdf)]
        )
    client.upload_cache_add.assert_not_called()
    client.create_taskbar.assert_not_called()
    client.update_taskbar.assert_not_called()


def test_no_customer_email_leaves_reply_fields_unfilled(tools: dict[str, Any], client: Mock) -> None:
    article = _reply_article(tools, client, [_article(4, sender="Agent")])
    assert article["in_reply_to"] == ""
    assert article["subtype"] == ""
    assert "to" not in article
