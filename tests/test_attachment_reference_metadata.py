"""Reject unsafe server metadata before downloading or writing."""

import pytest

from tests.attachment_reference_support import source_article

BAD_METADATA = [
    {"attachments": []},
    {"attachments": None},
    {"attachments": "invalid"},
    {"attachments": [{"id": 91}]},
    *[{"size": value} for value in (None, -1, True, 1.5, "-1", "many", 10 * 1024 * 1024 + 1)],
    *[
        {"filename": value}
        for value in (None, "", "../report.pdf", "/report.pdf", "a\\b.pdf", "a\x00b.pdf", "a\nb.pdf", ".", "..")
    ],
    {"id": True},
    {"id": "91"},
    {"id": 92},
    {"duplicate": True},
]


@pytest.mark.parametrize("change", BAD_METADATA)
def test_client_rejects_unsafe_attachment_metadata(attachment_api, change):
    client, api = attachment_api
    article = source_article()
    if "attachments" in change:
        article.update(change)
    elif "duplicate" in change:
        article["attachments"] *= 2
    else:
        article["attachments"][0].update(change)
    api.ticket_article.find.side_effect = lambda _identifier: article
    with pytest.raises(ValueError):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article_attachment.download.assert_not_called()
    api.ticket_article.create.assert_not_called()


def test_client_rejects_total_metadata_over_limit(attachment_api):
    client, api = attachment_api
    article = source_article()
    article["attachments"] = [
        {"id": identifier, "filename": "report.pdf", "size": 9 * 1024 * 1024} for identifier in (91, 92, 93)
    ]
    api.ticket_article.find.side_effect = lambda _identifier: article
    with pytest.raises(ValueError, match="25 MiB"):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91, 92, 93])
    api.ticket_article_attachment.download.assert_not_called()
    api.ticket_article.create.assert_not_called()
