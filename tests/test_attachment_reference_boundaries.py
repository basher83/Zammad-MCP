"""Exercise inclusive file and selection limits through the public client."""

import base64

import pytest

from tests.attachment_reference_support import source_article

MIB = 1024 * 1024


def sized_article(sizes):
    """Return selected metadata for exact byte-count boundaries."""
    article = source_article()
    article["attachments"] = [
        {"id": 91 + index, "filename": "file.bin", "size": size} for index, size in enumerate(sizes)
    ]
    return article


@pytest.mark.parametrize("sizes", [(0,), (10 * MIB,), (10 * MIB, 10 * MIB, 5 * MIB)])
def test_client_accepts_exact_size_boundaries(attachment_api, sizes):
    client, api = attachment_api
    article = sized_article(sizes)
    api.ticket_article.find.side_effect = lambda _identifier: article
    contents = [b"x" * size for size in sizes]
    api.ticket_article_attachment.download.side_effect = contents
    result = client.add_article(41, "Reuse", source_article_id=72, attachment_ids=list(range(91, 91 + len(sizes))))
    uploads = api.ticket_article.create.call_args.args[0]["attachments"]
    assert result["id"] == 73
    assert [base64.b64decode(upload["data"]) for upload in uploads] == contents
    assert api.ticket_article.create.call_count == 1


@pytest.mark.parametrize("sizes", [(10 * MIB + 1,), (10 * MIB, 10 * MIB, 5 * MIB + 1)])
def test_client_rejects_size_limits_exceeded_by_one_before_io(attachment_api, sizes):
    client, api = attachment_api
    article = sized_article(sizes)
    api.ticket_article.find.side_effect = lambda _identifier: article
    with pytest.raises(ValueError, match="MiB"):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=list(range(91, 91 + len(sizes))))
    api.ticket_article_attachment.download.assert_not_called()
    api.ticket_article.create.assert_not_called()


@pytest.mark.parametrize(
    "before,after", [(None, "2026-01-01T00:00:00Z"), ("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z")]
)
def test_client_rejects_timestamp_only_source_changes(attachment_api, before, after):
    client, api = attachment_api
    initial, changed = source_article(), source_article()
    initial["updated_at"], changed["updated_at"] = before, after
    api.ticket_article.find.side_effect = [initial, changed]
    with pytest.raises(ValueError, match="changed"):
        client.add_article(41, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.create.assert_not_called()
