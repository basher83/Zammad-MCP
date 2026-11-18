"""Supply fictional Zammad capabilities for attachment-reference tests."""

from unittest.mock import Mock, patch

import pytest

from mcp_zammad.client import ZammadClient


def source_article():
    """Return source metadata with no real customer data."""
    return {
        "id": 72,
        "ticket_id": 41,
        "attachments": [
            {"id": 91, "filename": "report.pdf", "size": 8, "preferences": {"Mime-Type": "application/pdf"}}
        ],
    }


def created_article():
    """Return a realistic API response without upload data."""
    return {
        "id": 73,
        "ticket_id": 41,
        "body": "See attached",
        "type": "email",
        "internal": False,
        "sender": "Agent",
        "created_by_id": 12,
        "updated_by_id": 12,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "attachments": [{"id": 92, "filename": "report.pdf", "size": 8, "content_type": "application/pdf"}],
    }


@pytest.fixture
def attachment_api(monkeypatch):
    """Provide the real client with a controlled external API boundary."""
    monkeypatch.setattr("requests.sessions.Session.request", reject_network)
    api = Mock()
    api.url = "https://example.invalid/api/v1/"
    api.session.request.side_effect = lambda *_args, **_kwargs: Mock(content=api.ticket_article_attachment.download())
    api.user.me.return_value = {"id": 12}
    api.ticket_article.find.side_effect = lambda _identifier: source_article()
    api.ticket_article_attachment.download.return_value = b"%PDF-1.7"
    api.ticket_article.create.return_value = created_article()
    with patch("mcp_zammad.client.ZammadAPI", return_value=api):
        client = ZammadClient(url="https://example.invalid/api/v1", http_token="fictional-token")
    return client, api


def reject_network(*_args, **_kwargs):
    """Fail if a reference test escapes its supplied API capabilities."""
    raise AssertionError("Network access is forbidden in attachment-reference tests")
