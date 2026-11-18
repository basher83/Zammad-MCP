"""Preserve attachment bytes, names, ordering, and MIME types."""

import base64

import pytest

from tests.attachment_reference_support import source_article


@pytest.mark.parametrize(
    "content,mime",
    [
        (b"%PDF-1.7", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xffdata", "image/jpeg"),
        (b"GIF89a", "image/gif"),
        (b"PK\x03\x04data", "application/zip"),
        (b"unknown", "application/octet-stream"),
        (b"", "application/octet-stream"),
    ],
)
def test_client_sniffs_magic_when_mime_metadata_is_absent(attachment_api, content, mime):
    client, api = attachment_api
    article = source_article()
    article["attachments"][0].update(size=len(content), filename="unrelated.extension", preferences={})
    api.ticket_article.find.side_effect = lambda _identifier: article
    api.ticket_article_attachment.download.return_value = content
    client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    uploaded = api.ticket_article.create.call_args.args[0]["attachments"][0]
    assert uploaded["mime-type"] == mime
    assert base64.b64decode(uploaded["data"]) == content


@pytest.mark.parametrize("mime_field", ["content_type", "mime-type", "mime_type"])
def test_client_preserves_mime_from_top_level_metadata(attachment_api, mime_field):
    client, api = attachment_api
    article = source_article()
    article["attachments"][0].pop("preferences")
    article["attachments"][0][mime_field] = "application/x-example; charset=binary"
    api.ticket_article.find.side_effect = lambda _identifier: article
    client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    assert (
        api.ticket_article.create.call_args.args[0]["attachments"][0]["mime-type"]
        == "application/x-example; charset=binary"
    )


def test_client_preserves_duplicate_names_and_requested_order(attachment_api):
    client, api = attachment_api
    article = source_article()
    article["attachments"] = [
        {"id": identifier, "filename": "résumé.pdf", "size": "8", "content_type": "application/pdf"}
        for identifier in (91, 92)
    ]
    api.ticket_article.find.side_effect = lambda _identifier: article
    api.ticket_article_attachment.download.side_effect = [b"%PDF-two", b"%PDF-one"]
    client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[92, 91])
    uploads = api.ticket_article.create.call_args.args[0]["attachments"]
    assert [item["filename"] for item in uploads] == ["résumé.pdf", "résumé.pdf"]
    assert [base64.b64decode(item["data"]) for item in uploads] == [b"%PDF-two", b"%PDF-one"]


@pytest.mark.parametrize(
    "change",
    [
        {"preferences": "invalid"},
        {"content_type": "text/plain"},
        {"preferences": {"Mime-Type": "bad\r\nmime"}},
        {"preferences": {"Mime-Type": 12}},
    ],
)
def test_client_rejects_invalid_or_conflicting_mime_metadata(attachment_api, change):
    client, api = attachment_api
    article = source_article()
    article["attachments"][0].update(change)
    api.ticket_article.find.side_effect = lambda _identifier: article
    with pytest.raises(ValueError):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.create.assert_not_called()
