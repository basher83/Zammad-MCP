"""Validate downloaded content and repeated reads before the single write."""

from copy import deepcopy

import pytest

from tests.attachment_reference_support import source_article


@pytest.mark.parametrize("content", [b"short", b"%PDF-1.7extra", b"x" * (10 * 1024 * 1024 + 1)])
def test_client_rejects_content_length_mismatch(attachment_api, content):
    client, api = attachment_api
    api.ticket_article_attachment.download.return_value = content
    with pytest.raises(ValueError, match="length"):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.create.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"ticket_id": 42},
        {"id": 74},
        {"attachments": []},
        {"filename": "changed.pdf"},
        {"size": 9},
        {"preferences": {"Mime-Type": "text/plain"}},
    ],
)
def test_client_rejects_changed_source_between_reads(attachment_api, change):
    client, api = attachment_api
    initial = source_article()
    changed = deepcopy(initial)
    if "filename" in change or "size" in change or "preferences" in change:
        changed["attachments"][0].update(change)
    else:
        changed.update(change)
    api.ticket_article.find.side_effect = [initial, changed]
    with pytest.raises(ValueError):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.create.assert_not_called()


@pytest.mark.parametrize("boundary", ["read", "download", "write"])
def test_client_reference_errors_do_not_expose_payloads(attachment_api, boundary):
    client, api = attachment_api
    capability = {
        "read": api.ticket_article.find,
        "download": api.ticket_article_attachment.download,
        "write": api.ticket_article.create,
    }[boundary]
    capability.side_effect = RuntimeError("Authorization: secret-fictional JVBERi0xLjc=")
    with pytest.raises(ValueError) as error:
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    assert "secret-fictional" not in str(error.value)
    assert "JVBERi0xLjc=" not in str(error.value)
    assert api.ticket_article.create.call_count == (1 if boundary == "write" else 0)


@pytest.mark.parametrize("article", [None, [], {"id": True, "ticket_id": 41}, {"id": 72, "ticket_id": "41"}])
def test_client_rejects_malformed_source_article(attachment_api, article):
    client, api = attachment_api
    api.ticket_article.find.side_effect = lambda _identifier: article
    with pytest.raises(ValueError):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.create.assert_not_called()


class MalformedCreateResponse:
    """Represent a conversion error containing fictional sensitive data."""

    def __iter__(self):
        raise ValueError("JVBERi0xLjc= Authorization: fictional-secret")


@pytest.mark.parametrize("response", [None, 0, ["malformed"], MalformedCreateResponse()])
def test_client_sanitizes_malformed_create_response_without_retry(attachment_api, response):
    client, api = attachment_api
    api.ticket_article.create.return_value = response
    with pytest.raises(ValueError, match=r"outcome unknown\. Do not retry automatically") as error:
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    assert "JVBERi0xLjc=" not in str(error.value)
    assert "fictional-secret" not in str(error.value)
    assert error.value.__suppress_context__
    assert api.ticket_article.create.call_count == 1
