"""Tests for KB answer search scope and legacy body extraction through public client methods."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_zammad.client import ZammadClient

BASE_URL = "https://zammad.example/api/v1/"


def _response(payload: dict[str, Any]) -> MagicMock:
    response = MagicMock(status_code=200, url=BASE_URL, content=b"{}")
    response.json.return_value = payload
    return response


def _category(category_id: int, answer_ids: list[int], child_ids: list[int]) -> MagicMock:
    return _response({"id": category_id, "answer_ids": answer_ids, "child_ids": child_ids})


def _answer(answer_id: int, translation_ids: list[int], translations: dict[str, Any]) -> MagicMock:
    answer = {"id": answer_id, "translation_ids": translation_ids}
    assets = {"KnowledgeBaseAnswer": {str(answer_id): answer}, "KnowledgeBaseAnswerTranslation": translations}
    return _response({"assets": assets})


@pytest.fixture
def client() -> ZammadClient:
    """Return a ZammadClient whose HTTP session is a controlled double."""
    with patch.dict("os.environ", {"ZAMMAD_URL": BASE_URL, "ZAMMAD_HTTP_TOKEN": "tok"}):
        zammad = ZammadClient()
    zammad.api.session = MagicMock()
    zammad.api.url = BASE_URL
    return zammad


def test_search_matches_body_in_descendant_category(client: ZammadClient) -> None:
    child_answer = _answer(3, [30], {"30": {"title": "Printer", "content_attributes": {"body": "<b>toner</b>"}}})
    client.api.session.get.side_effect = [
        _response({"id": 1, "category_ids": [5]}),
        _category(5, [], [6]),
        _category(6, [3], []),
        _category(5, [], [6]),
        _category(6, [3], []),
        child_answer,
        child_answer,
    ]

    results = client.search_kb_answers(1, "TONER")

    assert [(r["id"], r["_category_id"]) for r in results] == [(3, 6)]


def test_answer_body_uses_legacy_translation_when_translation_ids_are_stale(client: ZammadClient) -> None:
    legacy = {"42": {"title": "Hello", "content_attributes": {"body": "<p>Legacy body</p>"}}}
    client.api.session.get.side_effect = [_answer(7, [99], legacy), _answer(7, [99], legacy)]

    result = client.get_kb_answer_with_content(1, 7)

    assert result["title"] == "Hello"
    assert result["body"].strip() == "Legacy body"
