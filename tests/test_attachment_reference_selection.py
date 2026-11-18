"""Validate reference selection through public request and client contracts."""

import pytest
from pydantic import ValidationError

from mcp_zammad.models import ArticleCreate

INVALID_SELECTIONS = [
    {"source_article_id": 72},
    {"attachment_ids": [91]},
    {"source_article_id": 72, "attachment_ids": []},
    *[{"source_article_id": identifier, "attachment_ids": [91]} for identifier in (0, -1, True, "72", 72.0)],
    *[{"source_article_id": 72, "attachment_ids": [identifier]} for identifier in (0, -1, True, "91", 91.0)],
    {"source_article_id": 72, "attachment_ids": [91, 91]},
    {"source_article_id": 72, "attachment_ids": list(range(1, 12))},
    {"source_article_id": 72, "attachment_ids": [91], "attachments": []},
    {
        "source_article_id": 72,
        "attachment_ids": [91],
        "attachments": [{"filename": "inline.txt", "data": "eA==", "mime-type": "text/plain"}],
    },
]


@pytest.mark.parametrize("selection", INVALID_SELECTIONS)
def test_model_rejects_invalid_reference_selection(selection):
    with pytest.raises(ValidationError):
        ArticleCreate(ticket_id=41, body="Reuse", **selection)


@pytest.mark.parametrize("selection", INVALID_SELECTIONS[:-1])
def test_client_rejects_invalid_selection_before_io(attachment_api, selection):
    client, api = attachment_api
    with pytest.raises(ValueError):
        client.add_article(41, "Reuse", **selection)
    api.ticket_article.find.assert_not_called()
    api.ticket_article.create.assert_not_called()


@pytest.mark.parametrize("ticket_id", [0, -1, True, "41", 41.0])
def test_client_requires_strict_target_id_for_references(attachment_api, ticket_id):
    client, api = attachment_api
    with pytest.raises(ValueError):
        client.add_article(ticket_id, "Reuse", source_article_id=72, attachment_ids=[91])
    api.ticket_article.find.assert_not_called()
    api.ticket_article.create.assert_not_called()


@pytest.mark.parametrize("reference_first", [True, False])
@pytest.mark.parametrize("ticket_id", [True, "41", 41.0])
def test_model_rejects_raw_mapping_coercion_independent_of_key_order(reference_first, ticket_id):
    references = {"source_article_id": 72, "attachment_ids": [92, 91]}
    fields = {"ticket_id": ticket_id, "body": "Reuse", "type": "email"}
    mapping = {**references, **fields} if reference_first else {**fields, **references}
    with pytest.raises(ValidationError, match="strictly positive integer"):
        ArticleCreate.model_validate(mapping)


@pytest.mark.parametrize("reference_first", [True, False])
@pytest.mark.parametrize("type_field", ["type", "article_type"])
def test_model_preserves_raw_mapping_reference_order_and_type_alias(reference_first, type_field):
    references = {"source_article_id": 72, "attachment_ids": [92, 91]}
    fields = {"ticket_id": 41, "body": "Reuse", type_field: "email"}
    mapping = {**references, **fields} if reference_first else {**fields, **references}
    article = ArticleCreate.model_validate(mapping)
    assert article.ticket_id == 41
    assert article.attachment_ids == [92, 91]
    assert article.article_type.value == "email"


@pytest.mark.parametrize("ticket_id,expected", [(True, 1), ("41", 41), (41.0, 41)])
def test_model_retains_legacy_ticket_coercion_without_references(ticket_id, expected):
    article = ArticleCreate.model_validate({"ticket_id": ticket_id, "body": "Legacy", "type": "note"})
    assert article.ticket_id == expected
    assert article.article_type.value == "note"
